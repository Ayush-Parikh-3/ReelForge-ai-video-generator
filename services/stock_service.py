import os
import re
import urllib.parse
import logging
import requests
from PIL import Image, ImageDraw
from config import PIXABAY_API_KEY, DISALLOWED_TERMS, TEMP_DIR, DIMENSIONS

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

def extract_search_candidates(raw_query: str) -> list[str]:
    """
    Extracts high-yield 1-3 word keyword combinations for Pixabay.
    Pixabay works best with 1-3 simple terms rather than long sentences.
    """
    # Clean non-alphanumeric
    cleaned = re.sub(r'[,.\-_:;!?\'"]', ' ', raw_query.lower())
    words = [w for w in cleaned.split() if len(w) >= 3 and w not in DISALLOWED_TERMS]
    stop_words = {'the', 'and', 'with', 'from', 'into', 'that', 'this', 'have', 'been', 'were', 'will', 'cinematic', 'shot', 'view', 'scene', 'high', 'detail', '4k', '8k'}
    filtered = [w for w in words if w not in stop_words]

    candidates = []
    if len(filtered) >= 2:
        candidates.append(f"{filtered[0]} {filtered[1]}")
    if len(filtered) >= 3:
        candidates.append(f"{filtered[0]} {filtered[2]}")
    if filtered:
        candidates.append(filtered[0])
    if len(filtered) >= 3:
        candidates.append(" ".join(filtered[:3]))

    # Fallback default
    if not candidates:
        candidates = ["nature landscape"]

    return candidates

def is_safe_tags(tags_str: str) -> bool:
    """Checks tags string to ensure strictly safe family-friendly content."""
    tags = [t.strip().lower() for t in tags_str.split(",")]
    for t in tags:
        for term in DISALLOWED_TERMS:
            if term in t:
                return False
    return True

def search_pixabay_video(query: str, pixabay_key: str, aspect_ratio: str, output_path: str) -> bool:
    """
    Queries Pixabay Videos API for stock footage clips.
    Strictly enforces safesearch=true and safety checks.
    """
    key = (pixabay_key or os.getenv("PIXABAY_API_KEY", "") or PIXABAY_API_KEY).strip()
    if not key or len(key) < 5:
        return False

    candidates = extract_search_candidates(query)

    for q in candidates:
        encoded = urllib.parse.quote(q)
        url = f"https://pixabay.com/api/videos/?key={key}&q={encoded}&safesearch=true&video_type=all&per_page=6"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=8.0)
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                for hit in hits:
                    tags = hit.get("tags", "")
                    if not is_safe_tags(tags):
                        continue

                    videos = hit.get("videos", {})
                    # Ultra-fast resolution selection: prefer medium/small (1-3MB) instead of 50MB 4K files
                    stream_info = videos.get("medium") or videos.get("small") or videos.get("tiny") or videos.get("large")

                    if stream_info and stream_info.get("url"):
                        video_url = stream_info["url"]
                        dl = requests.get(video_url, headers=HEADERS, stream=True, timeout=16.0)
                        if dl.status_code == 200:
                            with open(output_path, "wb") as f:
                                for chunk in dl.iter_content(chunk_size=65536):
                                    if chunk:
                                        f.write(chunk)
                            if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                                logger.info(f"Downloaded Pixabay stock video for '{q}' (Hit ID: {hit.get('id')})")
                                return True
        except Exception as e:
            logger.warning(f"Pixabay video attempt for '{q}' notice: {e}")

    return False

def search_pixabay_photo(query: str, pixabay_key: str, width: int, height: int, output_path: str) -> bool:
    """
    Queries Pixabay Photos API for authentic high-resolution stock photography.
    Used when a direct video clip is unavailable.
    """
    key = (pixabay_key or os.getenv("PIXABAY_API_KEY", "") or PIXABAY_API_KEY).strip()
    if not key or len(key) < 5:
        return False

    candidates = extract_search_candidates(query)
    orientation = "horizontal" if width >= height else "vertical"

    for q in candidates:
        encoded = urllib.parse.quote(q)
        url = f"https://pixabay.com/api/?key={key}&q={encoded}&image_type=photo&orientation={orientation}&safesearch=true&per_page=6"

        try:
            resp = requests.get(url, headers=HEADERS, timeout=6.0)
            if resp.status_code == 200:
                hits = resp.json().get("hits", [])
                for hit in hits:
                    tags = hit.get("tags", "")
                    if not is_safe_tags(tags):
                        continue

                    img_url = hit.get("webformatURL") or hit.get("largeImageURL")
                    if img_url:
                        dl = requests.get(img_url, headers=HEADERS, timeout=8.0)
                        if dl.status_code == 200 and len(dl.content) > 5000:
                            with open(output_path, "wb") as f:
                                f.write(dl.content)
                            resize_and_crop(output_path, width, height)
                            logger.info(f"Downloaded Pixabay photo for '{q}' (Hit ID: {hit.get('id')})")
                            return True
        except Exception as e:
            logger.warning(f"Pixabay photo attempt for '{q}' notice: {e}")

    return False

def resize_and_crop(image_path: str, target_w: int, target_h: int):
    """Resizes and center-crops an image to target dimensions."""
    try:
        with Image.open(image_path) as im:
            im = im.convert("RGB")
            if im.size == (target_w, target_h):
                return
            im_ratio = im.size[0] / im.size[1]
            target_ratio = target_w / target_h

            if im_ratio > target_ratio:
                new_h = target_h
                new_w = int(target_h * im_ratio)
            else:
                new_w = target_w
                new_h = int(target_w / im_ratio)

            im_resized = im.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - target_w) // 2
            top = (new_h - target_h) // 2
            im_cropped = im_resized.crop((left, top, left + target_w, top + target_h))
            im_cropped.save(image_path, quality=94)
    except Exception as e:
        logger.warning(f"Image resize notice: {e}")

def create_minimalist_card(query: str, width: int, height: int, output_path: str) -> str:
    """Generates a clean matte minimalist scene card (NO neon, pure slate neutral)."""
    img = Image.new("RGB", (width, height), (16, 17, 20))
    draw = ImageDraw.Draw(img)

    for y in range(height):
        ratio = y / height
        r = int(14 + ratio * 8)
        g = int(16 + ratio * 8)
        b = int(20 + ratio * 10)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    pad = 40
    draw.rounded_rectangle(
        [pad, pad, width - pad, height - pad],
        radius=14,
        outline=(255, 255, 255, 20),
        width=1
    )

    clean_title = query.title()[:45]
    cx, cy = width // 2, height // 2
    draw.text((cx, cy - 10), clean_title, fill=(244, 244, 245), anchor="mm")
    draw.text((cx, cy + 24), "PIXABAY STOCK SCENE", fill=(140, 144, 155), anchor="mm")

    img.save(output_path, quality=92)
    return output_path

def get_scene_visual(
    query: str,
    scene_idx: int,
    aspect_ratio: str = "16:9",
    pixabay_key: str = None
) -> dict:
    """
    Primary stock visual retrieval pipeline using Pixabay (Videos & Photos):
    1. Pixabay Videos API (authentic video clips)
    2. Pixabay Photos API (authentic photography with Ken Burns cinematic motion)
    3. Minimalist Clean Card fallback
    NO Pollinations used!
    """
    dim = DIMENSIONS.get(aspect_ratio, DIMENSIONS["16:9"])
    w, h = dim["width"], dim["height"]

    video_path = os.path.join(TEMP_DIR, f"scene_{scene_idx}_footage.mp4")
    image_path = os.path.join(TEMP_DIR, f"scene_{scene_idx}_visual.jpg")

    # 1. Search Pixabay Videos
    if search_pixabay_video(query, pixabay_key, aspect_ratio, video_path):
        return {"type": "video", "path": video_path, "source": "pixabay_video"}

    # 2. Search Pixabay Photos
    if search_pixabay_photo(query, pixabay_key, w, h, image_path):
        return {"type": "image", "path": image_path, "source": "pixabay_photo"}

    # 3. Clean Card Fallback
    create_minimalist_card(query, w, h, image_path)
    return {"type": "image", "path": image_path, "source": "clean_card"}
