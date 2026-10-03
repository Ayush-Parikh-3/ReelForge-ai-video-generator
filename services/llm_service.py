import os
import re
import json
import logging
import requests
from config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert video director and scriptwriter.
Given any topic, question, or story idea, write an EXACT, ENGAGING, and HIGHLY PRACTICAL video script divided into distinct scenes.

CRITICAL INSTRUCTIONS:
1. Never write vague fluff or generic filler (never say "at the heart of X lies passion" or "across boundless horizons").
2. Write concrete, useful, spoken voiceover narration (18 to 28 words per scene, ~4-6 seconds per scene).
3. Directly answer or narrate the user's prompt (e.g., if user asks 'how to get marks in exam', provide real, tactical exam techniques: active recall, time allocation, reading questions twice, reviewing answers).
4. For each scene provide a 'stock_query' with 2-3 simple, visual keywords that Pixabay's video library can find easily (e.g. 'student studying', 'writing notes', 'classroom exam', 'clock ticking', 'happy graduate').

SCHEMA (Return valid JSON only):
{
  "title": "Clear Actionable Title",
  "scenes": [
    {
      "scene_id": 1,
      "narration": "Direct, spoken voiceover for scene 1...",
      "stock_query": "student studying desk"
    }
  ]
}
"""

def clean_json_response(raw_text: str) -> dict:
    """Extracts and safely parses JSON from an LLM response."""
    text = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        text = match.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end+1]

    # Clean trailing commas
    text_clean = re.sub(r",\s*([\]}])", r"\1", text)
    try:
        return json.loads(text_clean)
    except Exception:
        pass

    # Regex extraction fallback if JSON has minor syntax issues
    title_m = re.search(r'"title"\s*:\s*"([^"]+)"', text)
    title = title_m.group(1) if title_m else "Video Guide"

    scene_pattern = re.compile(
        r'\{\s*"scene_id"\s*:\s*(\d+)[\s\S]*?"narration"\s*:\s*"([^"]+)"[\s\S]*?"stock_query"\s*:\s*"([^"]+)"[\s\S]*?\}',
        re.DOTALL
    )
    scenes = []
    for m in scene_pattern.finditer(text):
        s_id = int(m.group(1))
        narr = m.group(2).replace('\\"', '"')
        query = m.group(3).replace('\\"', '"')
        scenes.append({
            "scene_id": s_id,
            "narration": narr,
            "stock_query": query,
            "visual_description": f"Stock footage matching {query}"
        })

    if scenes:
        return {"title": title, "scenes": scenes}

    raise ValueError("Could not parse valid scenes from LLM response")

def generate_script_gemini(prompt: str, scene_count: int = 4, api_key: str = None) -> dict:
    """
    Generates video script using Google Gemini API (gemini-2.0-flash / gemini-1.5-flash).
    Configured via GEMINI_API_KEY environment variable.
    """
    key = (api_key or os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY).strip()
    if not key:
        return None

    user_msg = f"""Topic/Question: "{prompt}"
REQUIRED SCENE COUNT: Exactly {scene_count} scenes (Numbered 1 to {scene_count}).
Provide concrete, actionable, highly relevant narration and 2-3 visual stock keywords per scene. Return valid JSON only."""

    models = ["gemini-2.0-flash", "gemini-1.5-flash", "gemini-2.5-flash"]
    last_err = None

    for model in models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": f"{SYSTEM_PROMPT}\n\n{user_msg}"}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "response_mime_type": "application/json"
                }
            }
            resp = requests.post(url, headers=headers, json=payload, timeout=18)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = clean_json_response(text)
                if parsed and parsed.get("scenes"):
                    logger.info(f"Successfully generated script via Gemini ({model}) with {len(parsed['scenes'])} scenes.")
                    return parsed
            else:
                last_err = f"Gemini {model} HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(last_err)
        except Exception as e:
            last_err = str(e)
            logger.warning(f"Gemini connection error with {model}: {e}")

    logger.warning(f"Gemini generation failed ({last_err}); falling back to exact semantic generator.")
    return None

def fallback_exact_script(prompt: str, scene_count: int = 4) -> dict:
    """
    Intelligent zero-fail script generator for when an API key is missing or offline.
    Directly understands the topic and generates exact, practical steps (never vague fluff).
    """
    clean_p = prompt.strip().lower()

    # 1. Custom Multi-line user script support
    raw_lines = [l.strip() for l in prompt.splitlines() if len(l.strip()) > 8]
    if len(raw_lines) >= 2:
        title = raw_lines[0][:40].strip()
        allocated_lines = [[] for _ in range(scene_count)]
        for i, line in enumerate(raw_lines):
            target_idx = min(i * scene_count // len(raw_lines), scene_count - 1)
            allocated_lines[target_idx].append(line)

        scenes = []
        for i in range(scene_count):
            narr = " ".join(allocated_lines[i]).strip() if allocated_lines[i] else f"Continuing with precision and clarity."
            words = re.findall(r'\b[A-Za-z]{3,}\b', narr)
            stop_words = {'the', 'and', 'with', 'from', 'into', 'that', 'this', 'have', 'been', 'were', 'will'}
            meaningful = [w for w in words if w.lower() not in stop_words]
            query = " ".join(meaningful[:2]) if meaningful else "focused study"
            scenes.append({
                "scene_id": i + 1,
                "narration": narr,
                "stock_query": query,
                "visual_description": f"Cinematic stock footage of {query}"
            })
        return {"title": title, "scenes": scenes}

    # 2. Topic Intent Detection
    # Domain: Exams / Study / Marks / Scoring / Grades
    if any(k in clean_p for k in ["exam", "mark", "study", "score", "grade", "test", "revise", "learn", "student"]):
        title = "Proven Strategy to Score High in Exams"
        steps = [
            ("Master the syllabus weightage first. Focus eighty percent of your energy on high-mark topics that appear consistently every year.", "student studying desk"),
            ("Use active recall instead of passive reading. Test yourself with flashcards and blank-sheet problem solving to lock concepts in memory.", "writing notes pen notebook"),
            ("Practice timed past papers under exam conditions. This builds rapid decision-making, speed, and eliminates test anxiety before the day.", "classroom student exam"),
            ("On exam day, read questions twice and allocate time strictly. Clear presentation, neat steps, and structured answers win every mark.", "happy student graduation success"),
            ("Review your paper in the final ten minutes. Catch simple arithmetic mistakes and verify all required questions are answered.", "clock ticking timer"),
            ("Consistent revision and calm execution turn average preparation into top percentile results.", "focused student library")
        ]
        selected = steps[:scene_count]
        scenes = [{"scene_id": i + 1, "narration": s[0], "stock_query": s[1]} for i, s in enumerate(selected)]
        return {"title": title, "scenes": scenes}

    # Domain: Coding / Programming / Software
    if any(k in clean_p for k in ["code", "coding", "python", "program", "software", "developer", "web", "computer"]):
        title = "The Developer's Blueprint: Build & Ship"
        steps = [
            ("Start by breaking complex problems into small, testable logic blocks. Clarity of thought comes before writing a single line of code.", "computer keyboard typing code"),
            ("Focus on core data structures and clean syntax. Write readable code that your future self and teammates can easily maintain.", "developer screen programming"),
            ("Learn by building real projects rather than watching endless tutorials. Hands-on debugging is where real engineering mastery happens.", "laptop coffee programmer desk"),
            ("Test relentlessly and embrace errors as feedback. Every bug solved deepens your problem-solving intuition and technical confidence.", "server room technology")
        ]
        selected = steps[:scene_count]
        scenes = [{"scene_id": i + 1, "narration": s[0], "stock_query": s[1]} for i, s in enumerate(selected)]
        return {"title": title, "scenes": scenes}

    # Domain: Fitness / Health / Gym / Nutrition
    if any(k in clean_p for k in ["fitness", "gym", "workout", "muscle", "weight", "diet", "health", "exercise"]):
        title = "Peak Performance: The Science of Physical Transformation"
        steps = [
            ("Consistency beats intensity every single time. Establish a regular routine that prioritizes progressive overload and proper lifting technique.", "gym workout barbell training"),
            ("Fuel your body with nutrient-dense whole foods and adequate protein to support cellular recovery and muscle synthesis.", "healthy food nutrition kitchen"),
            ("Prioritize deep sleep and active recovery. Your muscles and nervous system rebuild and grow stronger during restful downtime.", "athlete stretching running track"),
            ("Track measurable metrics over months, not days. Sustainable physical transformation is built on patience and disciplined daily habits.", "fitness runner sunrise horizon")
        ]
        selected = steps[:scene_count]
        scenes = [{"scene_id": i + 1, "narration": s[0], "stock_query": s[1]} for i, s in enumerate(selected)]
        return {"title": title, "scenes": scenes}

    # Domain: Business / Money / Productivity
    if any(k in clean_p for k in ["business", "money", "startup", "invest", "finance", "productivity", "focus"]):
        title = "Strategic Growth: Value Creation & Execution"
        steps = [
            ("Successful ventures solve acute, painful problems for specific people. Relentless focus on genuine customer value is the ultimate advantage.", "modern office meeting business"),
            ("Eliminate shallow distractions and dedicate uninterrupted blocks to high-leverage work that moves the needle forward.", "focused professional working laptop"),
            ("Manage capital with discipline. Reinvest in core distribution channels and build sustainable margins before scaling aggressively.", "financial charts stock market data"),
            ("Speed of execution and iterative feedback separate thriving businesses from forgotten ideas.", "city skyline sunset modern architecture")
        ]
        selected = steps[:scene_count]
        scenes = [{"scene_id": i + 1, "narration": s[0], "stock_query": s[1]} for i, s in enumerate(selected)]
        return {"title": title, "scenes": scenes}

    # 3. Dynamic General Topic Extractor
    words = re.findall(r'\b[A-Za-z]{3,}\b', prompt)
    stop_words = {'the', 'and', 'with', 'from', 'into', 'about', 'video', 'make', 'create', 'show', 'tell', 'story', 'explain', 'what', 'how', 'why'}
    keywords = [w for w in words if w.lower() not in stop_words]
    subject = " ".join(keywords[:3]) if keywords else prompt[:25]

    title = f"Mastering {subject.title()}: A Practical Guide"
    steps = [
        (f"Understanding the core fundamentals of {subject} requires cutting through noise to focus on what truly matters.", f"{keywords[0] if keywords else 'studying desk'}"),
        (f"By breaking down {subject} into manageable components, each step becomes clear, actionable, and repeatable.", f"{keywords[1] if len(keywords) > 1 else 'hands writing notebook'}"),
        (f"Consistent application and active practice solidify your understanding, turning theory into practical intuition.", "focused work modern desk"),
        (f"With sustained focus and clear execution, mastering {subject} unlocks new levels of achievement and progress.", "success sunlight sunrise")
    ]
    selected = steps[:scene_count]
    scenes = [{"scene_id": i + 1, "narration": s[0], "stock_query": s[1]} for i, s in enumerate(selected)]
    return {"title": title, "scenes": scenes}

def generate_script(prompt: str, scene_count: int = 4, gemini_api_key: str = None) -> dict:
    """
    Main script generation pipeline:
    1. Try Google Gemini API (GEMINI_API_KEY) if configured in environment or passed.
    2. Fallback to exact, topic-aware semantic generator (never random fluff).
    """
    gemini_key = (gemini_api_key or os.getenv("GEMINI_API_KEY", "") or GEMINI_API_KEY).strip()
    if gemini_key:
        script = generate_script_gemini(prompt, scene_count, gemini_key)
        if script and script.get("scenes"):
            return script

    return fallback_exact_script(prompt, scene_count)
