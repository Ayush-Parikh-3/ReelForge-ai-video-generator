import os
import subprocess
import logging
from config import FFMPEG_PATH, DIMENSIONS, SUBTITLE_STYLES, TEMP_DIR

logger = logging.getLogger(__name__)

def generate_ambient_music(duration: float, output_path: str):
    """Generates a pleasant, calming ambient background drone/synth bed."""
    dur_str = f"{max(3.0, duration):.1f}"
    # Soft warm ambient synth with subtle lowpass filter
    filter_complex = (
        f"anoisesrc=d={dur_str}:c=pink:r=44100:a=0.012,lowpass=f=300[noise];"
        f"sine=f=110:d={dur_str}[n1];"
        f"sine=f=164.81:d={dur_str}[n2];"
        f"sine=f=220:d={dur_str}[n3];"
        f"[n1][n2][n3]amix=inputs=3:dropout_transition=2[syn];"
        f"[syn]volume=0.05[synv];"
        f"[noise][synv]amix=inputs=2:dropout_transition=2,afade=t=in:ss=0:d=1.5,afade=t=out:st={duration-1.5:.1f}:d=1.5[out]"
    )
    cmd = [
        FFMPEG_PATH, "-y",
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", dur_str,
        output_path
    ]
    subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, errors="ignore")

def build_subtitle_filter(srt_file: str, aspect_ratio: str, style_name: str = "modern") -> str:
    """Builds clean, non-neon FFmpeg subtitle style configuration."""
    cfg = SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["modern"])
    font_size = 26 if aspect_ratio == "9:16" else 22
    margin_v = 110 if aspect_ratio == "9:16" else 35

    # Safe font selection across Windows and Linux
    sub_font = "Arial" if os.name == "nt" else "DejaVu Sans"

    primary_color = cfg.get("primary_color", "&H00FFFFFF")
    outline_color = cfg.get("outline_color", "&H00000000")
    back_color = cfg.get("back_color", "&H80000000")
    border_style = cfg.get("border_style", 4)
    outline = cfg.get("outline", 0)
    shadow = cfg.get("shadow", 0)

    # Use relative filename to avoid Windows colon/backslash escaping issues
    rel_srt = os.path.basename(srt_file)

    style_str = (
        f"FontName={sub_font},FontSize={font_size},Bold=1,"
        f"PrimaryColour={primary_color},OutlineColour={outline_color},"
        f"BackColour={back_color},BorderStyle={border_style},"
        f"Outline={outline},Shadow={shadow},Alignment=2,MarginV={margin_v}"
    )

    return f"subtitles={rel_srt}:force_style='{style_str}'"

def render_scene_video(
    visual_info: dict,
    audio_path: str,
    srt_path: str,
    output_path: str,
    duration: float,
    aspect_ratio: str = "16:9",
    scene_idx: int = 0,
    subtitle_style: str = "modern"
) -> bool:
    """
    Renders an individual scene clip combining footage/image + audio + subtitles.
    Handles both MP4 video clips (looping/scaling) and still photography (Ken Burns motion).
    """
    dim = DIMENSIONS.get(aspect_ratio, DIMENSIONS["16:9"])
    w, h = dim["width"], dim["height"]

    work_dir = os.path.dirname(os.path.abspath(audio_path))
    rel_audio = os.path.basename(audio_path)
    rel_out = os.path.basename(output_path)

    sub_filter = build_subtitle_filter(srt_path, aspect_ratio, subtitle_style)

    is_video = visual_info.get("type") == "video"
    raw_path = visual_info.get("path")
    rel_visual = os.path.basename(raw_path)

    if is_video:
        # Stock footage clip: scale & crop to target dimensions, loop if shorter than audio, trim to exact duration
        scale_filter = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
        vf = f"{scale_filter},{sub_filter}"

        cmd = [
            FFMPEG_PATH, "-y",
            "-stream_loop", "-1",
            "-i", rel_visual,
            "-i", rel_audio,
            "-vf", vf,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "26",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", "44100",
            "-b:a", "128k",
            "-t", f"{duration:.3f}",
            "-shortest",
            rel_out
        ]
    else:
        # Photography: apply smooth, cinematic camera motion (Ken Burns effect)
        motion_id = scene_idx % 3
        if motion_id == 0:
            # Slow subtle push-in (zoom 1.0 to 1.15)
            motion = f"zoompan=z='min(zoom+0.0016,1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps=24"
        elif motion_id == 1:
            # Subtle pull-out (1.15 to 1.0)
            motion = f"zoompan=z='if(lte(on,1),1.15,max(1.0,zoom-0.0016))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps=24"
        else:
            # Subtle horizontal drift
            motion = f"zoompan=z=1.10:x='min(on*1.2,iw-iw/zoom)':y='ih/2-(ih/zoom/2)':d=1:s={w}x{h}:fps=24"

        vf = f"{motion},{sub_filter}"

        cmd = [
            FFMPEG_PATH, "-y",
            "-loop", "1",
            "-i", rel_visual,
            "-i", rel_audio,
            "-vf", vf,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "26",
            "-r", "24",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-ar", "44100",
            "-b:a", "128k",
            "-t", f"{duration:.3f}",
            "-shortest",
            rel_out
        ]

    logger.info(f"Rendering scene {scene_idx} ({'video' if is_video else 'photo'}, {duration:.2f}s)...")
    res = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, errors="ignore")
    if res.returncode != 0:
        logger.warning(f"Scene render with subtitles failed: {res.stderr[-250:]}. Retrying without subtitle filter...")
        # Fallback: render without subtitle filter (player will display captions via HTML5 track)
        if is_video:
            clean_vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
            fb_cmd = [
                FFMPEG_PATH, "-y",
                "-stream_loop", "-1",
                "-i", rel_visual,
                "-i", rel_audio,
                "-vf", clean_vf,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "26",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-t", f"{duration:.3f}",
                "-shortest",
                rel_out
            ]
        else:
            clean_vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}"
            fb_cmd = [
                FFMPEG_PATH, "-y",
                "-loop", "1",
                "-i", rel_visual,
                "-i", rel_audio,
                "-vf", clean_vf,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "26",
                "-r", "24",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-t", f"{duration:.3f}",
                "-shortest",
                rel_out
            ]
        res_fb = subprocess.run(fb_cmd, cwd=work_dir, capture_output=True, text=True, errors="ignore")
        if res_fb.returncode != 0:
            logger.error(f"Fallback render failed: {res_fb.stderr[-250:]}")
            return False

    return os.path.exists(output_path) and os.path.getsize(output_path) > 1000

def concatenate_scenes(
    scene_clips: list,
    output_video: str,
    ambient_music_path: str = None
) -> bool:
    """
    Concatenates scene MP4 files into a single master video.
    Optionally overlays subtle ambient music mixed under narration.
    """
    if not scene_clips:
        return False

    concat_txt_path = os.path.join(TEMP_DIR, "concat_list.txt")
    with open(concat_txt_path, "w", encoding="utf-8") as f:
        for clip in scene_clips:
            clip_name = os.path.basename(clip)
            f.write(f"file '{clip_name}'\n")

    temp_concat = os.path.join(TEMP_DIR, "temp_concat.mp4")

    # Fast demuxer concatenation
    cmd_concat = [
        FFMPEG_PATH, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", "concat_list.txt",
        "-c", "copy",
        os.path.basename(temp_concat)
    ]
    res = subprocess.run(cmd_concat, cwd=TEMP_DIR, capture_output=True, text=True, errors="ignore")
    if res.returncode != 0:
        logger.warning(f"Direct stream copy concat failed; re-encoding concat: {res.stderr[-200:]}")
        cmd_concat_re = [
            FFMPEG_PATH, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", "concat_list.txt",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            os.path.basename(temp_concat)
        ]
        subprocess.run(cmd_concat_re, cwd=TEMP_DIR, capture_output=True, text=True, errors="ignore")

    if not os.path.exists(temp_concat):
        logger.error("Failed to generate concatenated video.")
        return False

    # Mix ambient background music if requested and available
    if ambient_music_path and os.path.exists(ambient_music_path):
        cmd_mix = [
            FFMPEG_PATH, "-y",
            "-i", temp_concat,
            "-i", ambient_music_path,
            "-filter_complex", "[0:a]volume=1.0[voice];[1:a]volume=0.12[bg];[voice][bg]amix=inputs=2:duration=first[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            output_video
        ]
        res_mix = subprocess.run(cmd_mix, capture_output=True, text=True, errors="ignore")
        if res_mix.returncode == 0 and os.path.exists(output_video):
            return True

    # If no music or mix failed, output concatenated video directly
    if os.path.exists(output_video):
        os.remove(output_video)
    os.rename(temp_concat, output_video)
    return True
