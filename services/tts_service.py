import os
import re
import asyncio
import subprocess
import logging
import edge_tts
from config import FFMPEG_PATH

logger = logging.getLogger(__name__)

def clean_speech_text(text: str) -> str:
    """Cleans text of markdown symbols, brackets, and quotes for natural speech."""
    t = re.sub(r"[*_~`#\[\](){}<>|\"]", "", text)
    t = re.sub(r"\s+", " ", t).strip()
    return t if t else "..."

def get_audio_duration(audio_path: str) -> float:
    """Extracts exact duration in seconds from an audio file using FFmpeg."""
    cmd = [FFMPEG_PATH, "-i", audio_path]
    res = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True, errors="ignore")
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", res.stderr)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))
        return hours * 3600 + minutes * 60 + seconds
    return 4.0

async def generate_speech_async(text: str, voice_id: str, output_path: str, rate: str = "+0%", pitch: str = "+0Hz"):
    """Synthesizes speech using Microsoft Edge neural TTS."""
    communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
    await communicate.save(output_path)

def generate_scene_audio(text: str, voice_id: str, output_path: str) -> tuple[float, str]:
    """Generates scene audio and returns (duration, cleaned_text)."""
    cleaned = clean_speech_text(text)
    asyncio.run(generate_speech_async(cleaned, voice_id, output_path))
    duration = get_audio_duration(output_path)
    return duration, cleaned

def format_srt_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS,mmm string for SRT format."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def format_vtt_time(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm string for WebVTT format."""
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

def generate_scene_srt(text: str, duration: float, output_srt_path: str) -> list:
    """
    Splits narration into 3-4 word punchy caption chunks with accurate timing.
    Returns list of subtitle segment dictionaries.
    """
    cleaned = clean_speech_text(text)
    words = cleaned.split()
    if not words:
        words = ["..."]

    chunk_size = 3 if len(words) <= 12 else 4
    chunks = []
    for i in range(0, len(words), chunk_size):
        chunks.append(" ".join(words[i:i+chunk_size]))

    total_chars = sum(max(2, len(c)) for c in chunks)
    srt_entries = []
    sub_segments = []
    current_time = 0.0

    for idx, chunk in enumerate(chunks):
        weight = len(chunk) / total_chars
        chunk_dur = max(0.8, duration * weight)
        start_t = current_time
        end_t = min(duration, current_time + chunk_dur)
        current_time = end_t

        srt_entries.append(
            f"{idx + 1}\n{format_srt_time(start_t)} --> {format_srt_time(end_t)}\n{chunk}\n"
        )
        sub_segments.append({
            "start": start_t,
            "end": end_t,
            "text": chunk
        })

    with open(output_srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_entries) + "\n")

    return sub_segments

def generate_master_vtt(scenes_info: list, output_vtt_path: str):
    """Generates a complete master WebVTT file for browser HTML5 video player."""
    vtt_lines = ["WEBVTT", ""]
    global_offset = 0.0

    cue_id = 1
    for s in scenes_info:
        subs = s.get("subtitles", [])
        for sub in subs:
            start_s = global_offset + sub["start"]
            end_s = global_offset + sub["end"]
            vtt_lines.append(f"{cue_id}")
            vtt_lines.append(f"{format_vtt_time(start_s)} --> {format_vtt_time(end_s)}")
            vtt_lines.append(sub["text"])
            vtt_lines.append("")
            cue_id += 1
        global_offset += s.get("duration", 0.0)

    with open(output_vtt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(vtt_lines))
