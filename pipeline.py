import os
import time
import uuid
import logging
import concurrent.futures
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
        scene_count: int = 3,
        aspect_ratio: str = "16:9",
        voice_id: str = "en-US-ChristopherNeural",
        subtitle_style: str = "modern",
        include_music: bool = True,
        gemini_api_key: str = None,
        pixabay_api_key: str = None,
        progress_callback=None
    ) -> dict:
        """
        Executes ultra-fast end-to-end text-to-video workflow:
        Parallel audio generation, parallel stock footage download, and parallel clip rendering.
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
        report("script", 10, "Writing script with Google Gemini AI...")

        # Step 1: Generate Script
        script_data = generate_script(prompt, scene_count, gemini_api_key)
        scenes = script_data.get("scenes", [])
        title = script_data.get("title", "AI Video Project")

        report("script", 25, f"Script ready: \"{title}\" ({len(scenes)} scenes).", {"script": script_data})

        # Step 2: Concurrently process all scenes in parallel
        report("production", 30, f"Generating {len(scenes)} scenes in parallel...")

        def process_scene(scene_tuple):
            idx, scene = scene_tuple
            scene_num = idx + 1
            narration = scene.get("narration", "")
            stock_query = scene.get("stock_query", "cinematic nature")

            # 1. Edge-TTS Audio synthesis
            audio_path = os.path.join(TEMP_DIR, f"{job_id}_scene_{scene_num}.mp3")
            duration, cleaned_text = generate_scene_audio(narration, voice_id, audio_path)

            # 2. Subtitles generation
            srt_path = os.path.join(TEMP_DIR, f"{job_id}_scene_{scene_num}.srt")
            sub_segments = generate_scene_srt(cleaned_text, duration, srt_path)

            # 3. Fast Stock Footage Retrieval (unique file per scene)
            visual_info = get_scene_visual(stock_query, f"{job_id}_{scene_num}", aspect_ratio, pixabay_api_key)

            # 4. Render Scene Clip with FFmpeg (ultrafast)
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

            return {
                "idx": idx,
                "scene_num": scene_num,
                "narration": narration,
                "stock_query": stock_query,
                "visual_info": visual_info,
                "duration": duration,
                "subtitles": sub_segments,
                "clip_path": clip_path if (rendered and os.path.exists(clip_path)) else None
            }

        scene_results = [None] * len(scenes)
        max_workers = min(4, max(1, len(scenes)))

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(process_scene, (i, s)): i for i, s in enumerate(scenes)
            }
            completed_count = 0
            for future in concurrent.futures.as_completed(future_to_idx):
                res = future.result()
                scene_results[res["idx"]] = res
                completed_count += 1
                pct = 30 + int((completed_count / len(scenes)) * 48)
                report("rendering", pct, f"Rendered Scene {res['scene_num']}/{len(scenes)} ({completed_count}/{len(scenes)} ready)...")

        scene_clips = [r["clip_path"] for r in scene_results if r and r.get("clip_path")]
        scenes_meta = [{
            "scene_id": r["scene_num"],
            "narration": r["narration"],
            "stock_query": r["stock_query"],
            "visual_type": r["visual_info"].get("type"),
            "visual_source": r["visual_info"].get("source"),
            "duration": r["duration"],
            "subtitles": r["subtitles"]
        } for r in scene_results if r]
        total_duration = sum(r["duration"] for r in scene_results if r)

        if not scene_clips:
            raise RuntimeError("Failed to render video clips for scenes.")

        # Step 3: Fast Background music (instant slice from pre-cached asset)
        music_path = None
        if include_music:
            report("audio", 82, "Adding subtle ambient audio bed...")
            music_path = os.path.join(TEMP_DIR, f"{job_id}_ambient.mp3")
            generate_ambient_music(total_duration, music_path)

        # Step 4: Stream Concat & Final Assembly
        report("assembly", 90, "Assembling complete master video...")
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
