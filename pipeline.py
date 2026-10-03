import os
import time
import uuid
import logging
from config import OUTPUT_DIR, TEMP_DIR
from services.llm_service import generate_script
from services.stock_service import get_scene_visual
from services.tts_service import generate_scene_audio, generate_scene_srt, generate_master_vtt
from services.video_service import render_scene_video, concatenate_scenes, generate_ambient_music

logger = logging.getLogger(__name__)

class VideoGenerationPipeline:
    def __init__(self):
        pass

    def run(
        self,
        prompt: str,
        scene_count: int = 4,
        aspect_ratio: str = "16:9",
        voice_id: str = "en-US-ChristopherNeural",
        subtitle_style: str = "modern",
        include_music: bool = True,
        gemini_api_key: str = None,
        pixabay_api_key: str = None,
        progress_callback=None
    ) -> dict:
        """
        Executes the full end-to-end text-to-video workflow.
        Returns metadata including video_url, script, duration, scene details.
        """
        def report(stage: str, percent: int, message: str, data: dict = None):
            if progress_callback:
                progress_callback({
                    "stage": stage,
                    "percent": percent,
                    "message": message,
                    "data": data or {}
                })
            logger.info(f"[{percent}%] {stage}: {message}")

        job_id = uuid.uuid4().hex[:10]
        report("script", 10, "Crafting exact script with Google Gemini AI...")

        # Step 1: Generate Script
        script_data = generate_script(prompt, scene_count, gemini_api_key)
        scenes = script_data.get("scenes", [])
        title = script_data.get("title", "AI Video Project")

        report("script", 25, f"Script generated: \"{title}\" with {len(scenes)} scenes.", {"script": script_data})

        scene_clips = []
        scenes_meta = []
        total_duration = 0.0

        # Step 2: Process each scene
        for idx, scene in enumerate(scenes):
            scene_num = idx + 1
            narration = scene.get("narration", "")
            stock_query = scene.get("stock_query", "cinematic nature")

            base_pct = 25 + int((idx / len(scenes)) * 50)
            report("voice", base_pct, f"Synthesizing voiceover for Scene {scene_num}/{len(scenes)}...")

            # Audio generation
            audio_path = os.path.join(TEMP_DIR, f"{job_id}_scene_{scene_num}.mp3")
            duration, cleaned_text = generate_scene_audio(narration, voice_id, audio_path)
            total_duration += duration

            # Subtitles generation
            srt_path = os.path.join(TEMP_DIR, f"{job_id}_scene_{scene_num}.srt")
            sub_segments = generate_scene_srt(cleaned_text, duration, srt_path)

            # Stock footage matching
            report("footage", base_pct + 5, f"Matching safe stock footage for Scene {scene_num} (\"{stock_query}\")...")
            visual_info = get_scene_visual(stock_query, scene_num, aspect_ratio, pixabay_api_key)

            # Render scene clip
            report("rendering", base_pct + 10, f"Composing Scene {scene_num} clip with subtitles...")
            clip_path = os.path.join(TEMP_DIR, f"{job_id}_scene_{scene_num}_clip.mp4")
            rendered = render_scene_video(
                visual_info=visual_info,
                audio_path=audio_path,
                srt_path=srt_path,
                output_path=clip_path,
                duration=duration,
                aspect_ratio=aspect_ratio,
                scene_idx=idx,
                subtitle_style=subtitle_style
            )

            if rendered and os.path.exists(clip_path):
                scene_clips.append(clip_path)

            scenes_meta.append({
                "scene_id": scene_num,
                "narration": narration,
                "stock_query": stock_query,
                "visual_type": visual_info.get("type"),
                "visual_source": visual_info.get("source"),
                "duration": duration,
                "subtitles": sub_segments
            })

        if not scene_clips:
            raise RuntimeError("Failed to render video clips for scenes.")

        # Step 3: Background music (optional)
        music_path = None
        if include_music:
            report("audio", 80, "Composing subtle ambient background music...")
            music_path = os.path.join(TEMP_DIR, f"{job_id}_ambient.mp3")
            generate_ambient_music(total_duration, music_path)

        # Step 4: Concatenation and Final Assembly
        report("assembly", 88, "Assembling complete master video...")
        output_filename = f"video_{job_id}.mp4"
        final_video_path = os.path.join(OUTPUT_DIR, output_filename)

        success = concatenate_scenes(scene_clips, final_video_path, music_path if include_music else None)
        if not success or not os.path.exists(final_video_path):
            raise RuntimeError("Final video assembly failed.")

        # Step 5: Master WebVTT for in-browser subtitle tracks
        vtt_filename = f"video_{job_id}.vtt"
        final_vtt_path = os.path.join(OUTPUT_DIR, vtt_filename)
        generate_master_vtt(scenes_meta, final_vtt_path)

        report("complete", 100, "Your video has been generated successfully!", {
            "video_filename": output_filename,
            "vtt_filename": vtt_filename,
            "title": title,
            "duration": round(total_duration, 1),
            "scenes": scenes_meta
        })

        return {
            "job_id": job_id,
            "title": title,
            "video_url": f"/output/{output_filename}",
            "vtt_url": f"/output/{vtt_filename}",
            "duration": round(total_duration, 1),
            "aspect_ratio": aspect_ratio,
            "scenes": scenes_meta
        }
