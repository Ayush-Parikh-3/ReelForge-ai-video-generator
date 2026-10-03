import os
import shutil
import imageio_ffmpeg
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Default API keys from environment
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "").strip()

# Ensure required directories exist
for directory in [STATIC_DIR, OUTPUT_DIR, TEMP_DIR, ASSETS_DIR]:
    os.makedirs(directory, exist_ok=True)

def get_ffmpeg_executable() -> str:
    """Finds FFmpeg on system PATH or falls back to bundled imageio-ffmpeg."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"

FFMPEG_PATH = get_ffmpeg_executable()

# Ensure FFmpeg directory is in PATH for any subprocesses
ffmpeg_dir = os.path.dirname(FFMPEG_PATH)
if ffmpeg_dir and ffmpeg_dir not in os.environ.get("PATH", ""):
    os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")

# Available High-Quality Edge-TTS Neural Voices
VOICES = [
    {"id": "en-US-ChristopherNeural", "name": "Christopher (US Male - Deep & Authoritative)", "gender": "male", "lang": "en-US"},
    {"id": "en-US-GuyNeural", "name": "Guy (US Male - Natural & Engaging)", "gender": "male", "lang": "en-US"},
    {"id": "en-US-JennyNeural", "name": "Jenny (US Female - Warm & Expressive)", "gender": "female", "lang": "en-US"},
    {"id": "en-US-AriaNeural", "name": "Aria (US Female - Crisp & Professional)", "gender": "female", "lang": "en-US"},
    {"id": "en-GB-RyanNeural", "name": "Ryan (UK Male - Cinematic Documentary)", "gender": "male", "lang": "en-GB"},
    {"id": "en-GB-SoniaNeural", "name": "Sonia (UK Female - Elegant Storyteller)", "gender": "female", "lang": "en-GB"},
    {"id": "en-IN-MadhurNeural", "name": "Madhur (Indian Male - Clear & Dynamic)", "gender": "male", "lang": "en-IN"},
    {"id": "en-IN-SwaraNeural", "name": "Swara (Indian Female - Friendly & Articulate)", "gender": "female", "lang": "en-IN"},
    {"id": "es-ES-AlvaroNeural", "name": "Alvaro (Spanish Male - Narrative)", "gender": "male", "lang": "es-ES"},
    {"id": "fr-FR-HenriNeural", "name": "Henri (French Male - Smooth & Rich)", "gender": "male", "lang": "fr-FR"},
    {"id": "de-DE-ConradNeural", "name": "Conrad (German Male - Deep & Confident)", "gender": "male", "lang": "de-DE"},
    {"id": "ja-JP-KeitaNeural", "name": "Keita (Japanese Male - Engaging)", "gender": "male", "lang": "ja-JP"},
]

# Aspect ratio dimensions
DIMENSIONS = {
    "16:9": {"width": 1280, "height": 720, "label": "Landscape (YouTube / Desktop)"},
    "9:16": {"width": 720, "height": 1280, "label": "Portrait (Reels / Shorts / TikTok)"}
}

# Subtitle visual styles
SUBTITLE_STYLES = {
    "modern": {
        "label": "Modern Pill (Clean white text on subtle translucent backing)",
        "font_size": 24,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H00000000",
        "back_color": "&H80000000",
        "border_style": 4, # Opaque box background
        "outline": 0,
        "shadow": 0
    },
    "cinematic": {
        "label": "Cinematic Minimalist (Crisp white with delicate dark shadow)",
        "font_size": 24,
        "primary_color": "&H00FFFFFF",
        "outline_color": "&H0018181B",
        "back_color": "&H00000000",
        "border_style": 1,
        "outline": 2.0,
        "shadow": 1.2
    },
    "highlight": {
        "label": "Warm Titanium (Subtle warm highlight with clean contrast)",
        "font_size": 24,
        "primary_color": "&H00F4F4F5",
        "outline_color": "&H0009090B",
        "back_color": "&H00000000",
        "border_style": 1,
        "outline": 2.5,
        "shadow": 1.5
    }
}

# Prohibited / Sensitive tags for strict content safety
DISALLOWED_TERMS = {
    "nude", "naked", "erotic", "nsfw", "sexy", "lingerie", "violence", "blood",
    "weapon", "kill", "gore", "harm", "hate", "abuse", "drugs", "suicide",
    "terror", "horror", "death", "corpse", "bikini", "cleavage", "sensual", "porn"
}
