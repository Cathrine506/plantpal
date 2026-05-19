"""
ai_service.py — PlantPal AI Chatbot Brain
==========================================

Call chain:
  1. Gemini 2.0 Flash  (free, 1500 req/day)
       ↓ rate-limited or key missing
  2. Groq + Llama 3.3 70B  (free, 30 req/min)
       ↓ rate-limited or key missing
  3. Smart rule engine  (always works offline)

Environment variables in .env:
  GEMINI_API_KEY   — aistudio.google.com (free, no card)
  GROQ_API_KEY     — console.groq.com   (free, no card)
"""

import os
import re
import requests

from services.plant_service import detect_plant, PLANT_PROFILES
from services.weather_service import assess_weather_risks

# ── API setup ────────────────────────────────────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "").strip()
GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "").strip()
GEMINI_AVAILABLE = bool(GEMINI_API_KEY)
GROQ_AVAILABLE   = bool(GROQ_API_KEY)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash:generateContent"
)
GROQ_URL   = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"

# Print once at startup so you can immediately see if keys are loaded
print(f"[PlantPal AI] Gemini available: {GEMINI_AVAILABLE}")
print(f"[PlantPal AI] Groq   available: {GROQ_AVAILABLE}")
if not GEMINI_AVAILABLE and not GROQ_AVAILABLE:
    print("[PlantPal AI] WARNING: No API keys found — running rule engine only.")
    print("[PlantPal AI] Add GEMINI_API_KEY to your .env file to enable AI responses.")


# =============================================================================
#  EXTENDED PLANT DATABASE  (covers plants not in plant_service.py)
# =============================================================================

EXTRA_PLANTS = {
    "rose": {
        "label": "Rose",
        "watering": "Every 2-3 days in summer, weekly in winter. Water deeply at the base — never on leaves. "
                    "Morning watering reduces fungal risk. Roses are thirsty plants; check soil daily in heat.",
        "sunlight": "Minimum 6 hours of direct sun daily. South or west-facing position is ideal. "
                    "Insufficient sun is the #1 cause of poor flowering.",
        "humidity": "Prefer moderate humidity (40-60%). High humidity causes black spot and powdery mildew. "
                    "Good air circulation is essential.",
        "temperature": "Thrive between 15-26°C. Below 0°C causes frost damage — mulch roots in winter. "
                       "Above 35°C stresses the plant; afternoon shade helps.",
        "fertiliser": "Feed every 2 weeks in spring/summer with rose-specific NPK (e.g. 5-10-5). "
                      "Stop feeding 6 weeks before first frost.",
        "diseases": "Black spot (dark circular spots with yellow halos — most common rose disease). "
                    "Powdery mildew (white coating on young leaves). Rose rust (orange pustules under leaves). "
                    "Treat all with neem oil or copper-based fungicide. Remove and bin affected leaves — never compost.",
        "pests": "Aphids (clustered on new growth — blast off with water, then neem oil). "
                 "Rose sawfly (skeletonises leaves — pick off by hand). Spider mites in dry heat.",
        "emergency": "Sudden yellowing of all leaves = likely black spot + stress. "
                     "No flowers = insufficient sun or needs feeding. Wilting despite watering = root issues or heat stress.",
        "watering_frequency_days": 2,
        "humidity_ideal": (40, 60),
        "temp_ideal": (15, 26),
    },
    "tomato": {
        "label": "Tomato Plant",
        "watering": "Every 1-2 days in warm weather — tomatoes need consistent moisture. "
                    "Inconsistent watering causes blossom end rot and fruit cracking. "
                    "Water deeply at the base; avoid wetting the leaves. Use a finger test — water when top inch is dry.",
        "sunlight": "Needs 8+ hours of full direct sun daily. Fewer hours = poor fruit set and low yields.",
        "humidity": "Prefer 65-75% humidity. Too high = fungal disease. "
                    "Shake plants gently in still air to help pollen release for fruit set.",
        "temperature": "Ideal 20-27°C. Below 10°C = no fruit set. Above 35°C = flowers drop without fruiting. "
                       "Protect from frost entirely.",
        "fertiliser": "High potassium feed (e.g. tomato fertiliser) once flowers appear. "
                      "Too much nitrogen before flowering = lots of leaves, no fruit.",
        "diseases": "Blight (brown/black patches on leaves and fruit — most serious tomato disease). "
                    "Blossom end rot (black sunken patch on fruit base — calcium deficiency from irregular watering). "
                    "Leaf curl (usually heat stress or water stress — not disease).",
        "pests": "Tomato hornworm (large green caterpillar — pick off by hand). "
                 "Whitefly and aphids (neem oil). Red spider mite in hot dry conditions.",
        "emergency": "Flowers dropping = too hot (above 35°C) or cold (below 10°C) or humidity too low. "
                     "Black patch on fruit bottom = blossom end rot — water more consistently. "
                     "Brown spreading patches on leaves = blight — act immediately with copper fungicide.",
        "watering_frequency_days": 2,
        "humidity_ideal": (65, 75),
        "temp_ideal": (20, 27),
    },
    "tulsi": {
        "label": "Tulsi (Holy Basil)",
        "watering": "Every 1-2 days in warm weather — prefers consistently moist soil. "
                    "Water when top inch feels dry. Do not let it sit in waterlogged soil.",
        "sunlight": "Loves full sun — minimum 6 hours daily. Grows fastest in direct sun.",
        "humidity": "Prefers moderate humidity (50-70%). Mulch around base to retain moisture.",
        "temperature": "Tropical plant — thrives at 20-35°C. Damaged below 10°C. Keep indoors in winter.",
        "fertiliser": "Light feeding with balanced liquid fertiliser every 2-3 weeks. Heavy feeding reduces aromatic oil content.",
        "diseases": "Powdery mildew in poor airflow. Root rot if overwatered.",
        "pests": "Aphids and spider mites. Neem oil spray is safe and effective.",
        "emergency": "Wilting despite moist soil = root rot or heat stress. "
                     "Leggy growth = not enough sun. Yellowing lower leaves = overwatering.",
        "watering_frequency_days": 2,
        "humidity_ideal": (50, 70),
        "temp_ideal": (20, 35),
    },
    "chilli": {
        "label": "Chilli Plant",
        "watering": "Every 2-3 days. Let top inch dry between watering. Overwatering is the main killer.",
        "sunlight": "6-8 hours full sun minimum. More sun = hotter, more prolific chillies.",
        "humidity": "50-70% preferred. In Bangalore's monsoon season, ensure good drainage and airflow.",
        "temperature": "Ideal 20-30°C. Fruit production slows below 15°C or above 35°C.",
        "fertiliser": "High phosphorus and potassium once flowering starts. Avoid excess nitrogen.",
        "diseases": "Anthracnose (dark sunken spots on fruit). Powdery mildew. Phytophthora root rot.",
        "pests": "Thrips, aphids, whitefly, mites. Neem oil spray weekly as prevention.",
        "emergency": "Flower drop = temperature extreme or inconsistent watering. "
                     "Fruit turning black = anthracnose — remove and treat immediately.",
        "watering_frequency_days": 2,
        "humidity_ideal": (50, 70),
        "temp_ideal": (20, 30),
    },
    "basil": {
        "label": "Basil",
        "watering": "Every 1-2 days — basil wilts dramatically when thirsty. "
                    "Water deeply in the morning at the base. Never let it sit in water.",
        "sunlight": "6+ hours of direct sun. Indoors, needs a very bright south-facing window.",
        "humidity": "50-70%. Hates cold draughts.",
        "temperature": "18-30°C. Dies below 10°C. Do not refrigerate fresh basil.",
        "fertiliser": "Light feeding every 3-4 weeks. Heavy feeding reduces flavour.",
        "diseases": "Fusarium wilt (sudden wilting, brown streaks in stem). Downy mildew (yellowing, grey fuzz under leaves).",
        "pests": "Aphids and Japanese beetles. Hand-pick or neem oil.",
        "emergency": "Sudden total wilting = fusarium wilt (no cure — remove and discard). "
                     "Pinch off flower heads to extend leaf production.",
        "watering_frequency_days": 1,
        "humidity_ideal": (50, 70),
        "temp_ideal": (18, 30),
    },
}

# Extended keyword map for detect_plant fallback
EXTRA_KEYWORD_MAP = {
    "rose": "rose", "roses": "rose",
    "tomato": "tomato", "tomatoes": "tomato",
    "tulsi": "tulsi", "holy basil": "tulsi", "basil tulsi": "tulsi",
    "chilli": "chilli", "chili": "chilli", "pepper": "chilli",
    "basil": "basil", "sweet basil": "basil",
}


def resolve_plant(plant_name: str, message: str = "") -> dict:
    """
    Try to find a plant profile. Checks:
    1. Extra plants (roses, tomatoes, etc.)
    2. Built-in plant_service profiles
    3. Falls back to default
    Returns (profile_dict, plant_label_string)
    """
    search = (plant_name + " " + message).lower()
    for keyword, key in EXTRA_KEYWORD_MAP.items():
        if keyword in search:
            return EXTRA_PLANTS[key]
    return detect_plant(plant_name or message)


# =============================================================================
#  INTENT CLASSIFICATION
# =============================================================================

INTENT_KEYWORDS = {
    "watering":    ["water", "watering", "irrigat", "thirsty", "dry soil", "wet soil",
                    "overwater", "underwater", "soggy", "drench", "how often", "when to water"],
    "sunlight":    ["sun", "light", "shade", "bright", "dark", "window", "uv",
                    "bleach", "scorch", "leggy", "etiolat", "sunlight"],
    "humidity":    ["humid", "mist", "spray", "dry air", "moisture", "vapour",
                    "crispy tips", "brown tips"],
    "temperature": ["temp", "cold", "hot", "heat", "warm", "freez", "chill",
                    "draught", "draft", "frost", "weather affect"],
    "fertiliser":  ["fertiliz", "fertilise", "feed", "nutrient", "npk",
                    "nitrogen", "phosphor", "potassium", "compost", "slow release", "feeding"],
    "disease":     ["disease", "sick", "spot", "yellow", "wilt", "droop", "dying",
                    "brown", "rot", "fungal", "blight", "mould", "mold",
                    "black", "mushy", "soft stem", "leaves falling", "leaves dropping",
                    "something wrong", "not looking good", "unhealthy"],
    "pest":        ["pest", "bug", "mite", "aphid", "mealybug", "spider",
                    "scale", "insect", "infest", "webbing", "sticky",
                    "white fluff", "gnats", "flies", "crawl"],
    "travel":      ["travel", "trip", "vacation", "holiday", "away", "leave",
                    "skip", "absent", "gone", "going away", "days away"],
    "emergency":   ["dying", "dead", "emergency", "urgent", "save",
                    "killing", "collapse", "wilting badly", "sudden",
                    "overnight", "help me", "please help", "what do i do"],
    "recovery":    ["recover", "revive", "better", "improving",
                    "progress", "bounce back", "coming back"],
    "greeting":    ["hello", "hi ", " hi", "^hi$", "hey", "good morning", "good evening",
                    "what can you", "can u talk", "are you there", "you there"],
    "care":        ["care", "tips", "advice", "how to", "guide", "maintain",
                    "routine", "schedule", "best way", "help me", "take care",
                    "look after", "grow", "keep"],
    "identity":    ["who are you", "what are you", "what do you do", "your name",
                    "introduce", "call me", "my name is", "i am "],
    "reminder":    ["remind", "reminder", "notification", "alert", "set alarm",
                    "every day", "daily", "schedule reminder", "notify me"],
    "gratitude":   ["thank", "thanks", "appreciate", "helpful", "great",
                    "awesome", "perfect", "brilliant", "good job"],
    "ok_check":    ["is my plant ok", "is it ok", "how is my plant", "plant doing",
                    "plant healthy", "plant fine", "plant alright"],
    "diagnosis":   ["diagnos", "what is", "why is", "why are", "why does",
                    "what wrong", "identify", "scan", "check", "what's happening",
                    "tell me why", "reason"],
    "repotting":   ["repot", "pot", "transplant", "roots coming out",
                    "root bound", "too small", "potting mix", "new pot"],
    "propagation": ["propagat", "cutting", "grow new", "multiply", "clone",
                    "baby plant", "pup", "offset", "division"],
}

INTENT_PRIORITY = [
    "identity", "reminder", "gratitude", "greeting",
    "emergency", "disease", "pest", "diagnosis", "ok_check",
    "watering", "sunlight", "humidity", "temperature",
    "fertiliser", "repotting", "propagation",
    "travel", "recovery", "care",
]


def classify_intent(message: str) -> str:
    msg = message.lower()
    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = 0
        for kw in keywords:
            if kw.startswith("^") or kw.endswith("$"):
                # regex keyword
                if re.search(kw, msg):
                    score += 2
            elif kw in msg:
                score += 1
        scores[intent] = score

    for intent in INTENT_PRIORITY:
        if scores.get(intent, 0) > 0:
            return intent
    return "care"


def extract_entities(message: str) -> dict:
    entities = {}

    all_plant_keywords = {
        **{k: v for k, v in EXTRA_KEYWORD_MAP.items()},
        "monstera": "monstera", "swiss cheese": "monstera",
        "snake plant": "snake_plant", "sansevieria": "snake_plant",
        "peace lily": "peace_lily", "spathiphyllum": "peace_lily",
        "pothos": "pothos", "devil's ivy": "pothos",
        "aloe vera": "aloe_vera", "aloe": "aloe_vera",
        "zz plant": "zz_plant", "zamioculcas": "zz_plant",
        "fiddle leaf": "fiddle_leaf_fig",
        "spider plant": "spider_plant",
        "succulent": "succulent", "cactus": "succulent",
    }
    for keyword, key in all_plant_keywords.items():
        if keyword in message.lower():
            entities["plant"] = key
            break

    days_match = re.search(r"(\d+)\s*day", message.lower())
    if days_match:
        entities["days"] = int(days_match.group(1))

    # Extract name if user introduces themselves
    name_match = re.search(
        r"(?:call me|my name is|i am|i'm)\s+([A-Za-z]+)", message, re.IGNORECASE
    )
    if name_match:
        entities["user_name"] = name_match.group(1).capitalize()

    symptoms = [
        sym for sym in
        ["yellow", "brown", "wilting", "drooping", "spotted", "mushy",
         "crispy", "pale", "black", "soft", "dying", "falling"]
        if sym in message.lower()
    ]
    if symptoms:
        entities["symptoms"] = symptoms

    return entities


# =============================================================================
#  SYSTEM PROMPT  (shared by Gemini + Groq)
# =============================================================================

def build_system_prompt(plant_name: str, weather: dict, scan: dict) -> str:
    plant = resolve_plant(plant_name)
    label = plant["label"]

    if weather:
        risks = assess_weather_risks(weather)
        risk_lines = (
            "\n".join(f"  - [{r['level'].upper()}] {r['message']}" for r in risks)
            if risks else "  - No significant risks detected."
        )
        weather_block = f"""
## Live Weather ({weather.get('city', 'your area')})
- Temp: {weather.get('temp', '--')}°C | Humidity: {weather.get('humidity', '--')}% | UV: {weather.get('uvIndex', '--')} | Conditions: {weather.get('description', '--')}
Active risks:
{risk_lines}
"""
    else:
        weather_block = "\n## Weather: Not available\n"

    if scan and scan.get("label"):
            conf = scan.get("confidence", 0)
            disease = scan.get("disease", "")
            d_conf = scan.get("disease_confidence", 0)
            source = scan.get("source", "local_model")
            scan_block = f"""
    ## Scan Result
    - Plant identified: {scan['label']} ({round(conf * 100)}% confidence)
    - Disease detected: {disease if disease else 'None detected'}{f" ({round(d_conf * 100)}% confidence)" if d_conf else ""}
    - Source: {source}
    - {'State confidently' if conf > 0.8 else 'Say "the scan suggests..."' if conf > 0.6 else 'Ask follow-ups before diagnosing'}
    """
    else:
            scan_block = "\n## Scan: Not performed yet — encourage user to upload a leaf photo\n"

    return f"""You are PlantPal, a friendly and expert AI Plant Agronomist. You help people take care of their plants with warm, personalised, science-backed advice.

## Your style
- Warm and conversational — like a knowledgeable friend, not a textbook
- Always explain WHY, not just what to do
- If someone introduces themselves, use their name naturally in replies
- If someone asks if you can talk / who you are — respond naturally and warmly
- If someone asks for a reminder (e.g. "remind me to water every 3 days") — you cannot set device reminders, but warmly explain this and suggest alternatives like phone alarms or sticky notes
- Use 1-2 emoji per reply max
- For problems, give 3-5 numbered action steps
- End with a helpful tip or follow-up question

## Plants you know about
You are an expert on ALL plants — not just houseplants. This includes roses, tomatoes, tulsi, chillies, herbs, vegetables, fruit trees, succulents, and any other plant the user mentions. If you don't have specific profile data, use your general plant expertise.

## Multi-modal reasoning
When you have BOTH scan AND weather data, combine them:
- Brown spots + humidity > 80% → STRONG fungal indicator
- Wilting + temp > 35°C → heat stress
- Yellowing + humidity < 40% → dry air or underwatering
- Crispy + UV ≥ 8 → sun scorch

## Memory
The full conversation history is provided. Always reference what was already said. Never ask for info already given.

## Current plant: {label}
Watering: {plant['watering']}
Sunlight: {plant['sunlight']}
Humidity: {plant['humidity']}
Temperature: {plant['temperature']}
Fertilising: {plant['fertiliser']}
Diseases: {plant['diseases']}
Pests: {plant['pests']}
Emergency signs: {plant['emergency']}
{weather_block}{scan_block}
Keep responses focused. Use numbered lists only for step-by-step actions. No need for headers in every reply."""


# =============================================================================
#  MAIN ENTRY POINT
# =============================================================================

def chat_with_ai(
    message: str,
    history: list,
    weather: dict,
    scan: dict,
    plant_name: str,
) -> dict:
    intent   = classify_intent(message)
    entities = extract_entities(message)
    if plant_name and "plant" not in entities:
        entities["plant"] = plant_name

    # Try Gemini → Groq → rule engine
    if GEMINI_AVAILABLE:
        result = _gemini_chat(message, history, weather, scan, plant_name, intent, entities)
        if result:
            return result

    if GROQ_AVAILABLE:
        result = _groq_chat(message, history, weather, scan, plant_name, intent, entities)
        if result:
            return result

    return _rule_fallback(message, history, weather, scan, plant_name, intent, entities)


# =============================================================================
#  GEMINI 2.0 FLASH  (primary)
# =============================================================================

def _gemini_chat(message, history, weather, scan, plant_name, intent, entities) -> dict | None:
    system_prompt = build_system_prompt(plant_name or message, weather, scan)

    contents = [
        {"role": "user",  "parts": [{"text": f"[SYSTEM]\n{system_prompt}"}]},
        {"role": "model", "parts": [{"text": "Understood. I am PlantPal, ready to help!"}]},
    ]
    for h in (history or [])[-18:]:
        if not isinstance(h, dict):
            continue
        role = h.get("role")
        if role == "user":
            contents.append({"role": "user",  "parts": [{"text": h.get("content", "")}]})
        elif role == "assistant":
            contents.append({"role": "model", "parts": [{"text": h.get("content", "")}]})

    contents.append({"role": "user", "parts": [{"text": message}]})

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.75, "maxOutputTokens": 600, "topP": 0.9},
        "safetySettings": [
            {"category": c, "threshold": "BLOCK_ONLY_HIGH"} for c in [
                "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT",
            ]
        ],
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if resp.status_code == 429:
            print("[PlantPal AI] Gemini rate limit — trying Groq")
            return None
        if resp.status_code == 400:
            print(f"[PlantPal AI] Gemini 400 error: {resp.text[:300]}")
            return None
        if resp.status_code == 403:
            print("[PlantPal AI] Gemini 403 — check your GEMINI_API_KEY in .env")
            return None

        resp.raise_for_status()
        data  = resp.json()
        reply = (
            data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
                .strip()
        )
        if not reply:
            print("[PlantPal AI] Gemini returned empty reply")
            return None

        print(f"[PlantPal AI] Gemini replied OK (intent={intent})")
        return {
            "response": reply, "confidence": 0.93, "intent": intent,
            "suggestions": _generate_suggestions(intent, plant_name, weather),
            "severity": _estimate_severity(intent, scan, weather),
            "source": "gemini-2.0-flash",
        }
    except requests.exceptions.Timeout:
        print("[PlantPal AI] Gemini timed out — trying Groq")
        return None
    except Exception as e:
        print(f"[PlantPal AI] Gemini error: {e}")
        return None


# =============================================================================
#  GROQ + LLAMA 3.3 70B  (secondary)
# =============================================================================

def _groq_chat(message, history, weather, scan, plant_name, intent, entities) -> dict | None:
    system_prompt = build_system_prompt(plant_name or message, weather, scan)

    messages = [{"role": "system", "content": system_prompt}]
    for h in (history or [])[-18:]:
        if isinstance(h, dict) and h.get("role") in ("user", "assistant"):
            messages.append({"role": h["role"], "content": h.get("content", "")})
    messages.append({"role": "user", "content": message})

    payload = {
        "model": GROQ_MODEL, "messages": messages,
        "max_tokens": 600, "temperature": 0.75, "top_p": 0.9,
    }

    try:
        resp = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        if resp.status_code == 429:
            print("[PlantPal AI] Groq rate limit — using rule engine")
            return None
        if resp.status_code in (401, 403):
            print("[PlantPal AI] Groq auth error — check GROQ_API_KEY in .env")
            return None

        resp.raise_for_status()
        data  = resp.json()
        reply = (
            data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
        )
        if not reply:
            print("[PlantPal AI] Groq returned empty reply")
            return None

        print(f"[PlantPal AI] Groq replied OK (intent={intent})")
        return {
            "response": reply, "confidence": 0.88, "intent": intent,
            "suggestions": _generate_suggestions(intent, plant_name, weather),
            "severity": _estimate_severity(intent, scan, weather),
            "source": "groq-llama3.3-70b",
        }
    except requests.exceptions.Timeout:
        print("[PlantPal AI] Groq timed out — using rule engine")
        return None
    except Exception as e:
        print(f"[PlantPal AI] Groq error: {e}")
        return None


# =============================================================================
#  SMART RULE ENGINE  (always-available fallback)
# =============================================================================

def _prev_user_topics(history: list) -> list[str]:
    words = []
    for h in (history or []):
        if isinstance(h, dict) and h.get("role") == "user":
            words.extend(h.get("content", "").lower().split())
    return words


def _rule_fallback(message, history, weather, scan, plant_name, intent, entities) -> dict:
    # Use message text to also help resolve plant if not selected from dropdown
    plant = resolve_plant(plant_name or "", message)
    label = plant["label"]

    w    = weather or {}
    temp = w.get("temp")
    hum  = w.get("humidity")
    uv   = w.get("uvIndex")
    city = w.get("city", "your area")

    scan_label = (scan or {}).get("label", "").lower()
    scan_conf  = (scan or {}).get("confidence", 0)
    prev_words = _prev_user_topics(history)
    user_name  = entities.get("user_name", "")

    greeting = f"Hi {user_name}! " if user_name else ""
    reply = ""

    # ── Special intents ───────────────────────────────────────────────────────

    if intent == "identity":
        msg_lower = message.lower()
        if any(x in msg_lower for x in ["call me", "my name is", "i am ", "i'm "]):
            name = entities.get("user_name", "")
            reply = (
                f"Nice to meet you{', ' + name if name else ''}! 😊 I'm PlantPal — your AI plant care assistant. "
                f"I can help you water, diagnose diseases, deal with pests, handle weather changes, "
                f"and keep any plant happy. What plant are you growing?"
            )
        else:
            reply = (
                "I'm PlantPal, your AI Plant Agronomist! 🌿 I'm here to help you keep your plants healthy "
                "and thriving. I can answer questions about watering, sunlight, diseases, pests, fertilising, "
                "weather care, and more — for any plant you're growing. What can I help you with?"
            )

    elif intent == "reminder":
        days_match = re.search(r"(\d+)\s*day", message.lower())
        days = days_match.group(1) if days_match else "few"
        reply = (
            f"I'd love to remind you, but unfortunately I can't send notifications or set alarms "
            f"on your device — I only live inside this chat window. 😅\n\n"
            f"Here's what I'd suggest instead:\n"
            f"1. Set a repeating alarm on your phone every {days} day(s) labelled 'Water plant'\n"
            f"2. Put a sticky note near your plant\n"
            f"3. Use a free app like 'Greg' or 'Planta' which are built specifically for plant watering reminders\n\n"
            f"For your {label}, here's when to water: {plant['watering'][:150]}..."
        )

    elif intent == "greeting":
        weather_note = f" It's {temp}°C and {hum}% humidity in {city} right now." if weather else ""
        reply = (
            f"{greeting}Hello! I'm PlantPal, your AI Plant Agronomist.{weather_note} "
            f"Tell me what plant you're growing and what's on your mind — "
            f"I can help with watering, diseases, pests, weather care, and much more! 🌿"
        )

    elif intent == "gratitude":
        reply = (
            f"You're very welcome{', ' + user_name if user_name else ''}! "
            f"Your plant is lucky to have such an attentive owner. "
            f"Feel free to come back any time — happy growing! 🌱"
        )

    elif intent == "ok_check":
        # "is my plant ok?" type questions — need context to answer
        if scan_label:
            conf_pct = round(scan_conf * 100)
            if scan_label == "healthy":
                reply = (
                    f"Great news! The scan shows your {label} looks **Healthy** ({conf_pct}% confidence). "
                    f"Keep up the good care routine. "
                    + (f"One thing to watch: with {hum}% humidity in {city}, {_humidity_tip(hum, label)}." if hum else "")
                )
            else:
                reply = (
                    f"The scan detected **{scan_label}** on your {label} ({conf_pct}% confidence). "
                    f"This needs attention. Here's what to do:\n\n{plant['diseases']}\n\n"
                    f"Would you like a step-by-step treatment plan?"
                )
        elif any(w in prev_words for w in ["yellow", "brown", "wilting", "spots", "drooping"]):
            reply = (
                f"Based on what you mentioned earlier about {', '.join([w for w in prev_words if w in ['yellow', 'brown', 'wilting', 'spots', 'drooping']][:3])}, "
                f"your {label} may need some attention. "
                f"The most likely causes are: {plant['diseases'][:200]}...\n\n"
                f"Upload a photo of the leaf for a more accurate diagnosis!"
            )
        else:
            temp_info = f"At {temp}°C in {city}, " if temp else ""
            reply = (
                f"{temp_info}without seeing your plant it's hard to say for certain, but here's "
                f"what a healthy {label} looks like: firm leaves, good colour, moist (not soggy) soil. "
                f"Any specific symptoms you've noticed? Or upload a photo and I'll scan it for you. 🔍"
            )

    # ── Multi-modal fusion ────────────────────────────────────────────────────
    elif scan_label and weather and intent in ("disease", "diagnosis", "emergency"):
        if ("fungal" in scan_label or "spotted" in scan_label) and hum and hum > 80:
            reply = (
                f"The scan detected **{scan_label}** ({round(scan_conf*100)}% confidence) combined "
                f"with {hum}% humidity in {city} — this strongly points to **fungal infection**.\n\n"
                f"1. Stop watering immediately — let soil dry out completely\n"
                f"2. Remove all affected leaves with sterilised scissors\n"
                f"3. Improve airflow around the plant\n"
                f"4. Spray with neem oil or copper-based fungicide\n"
                f"5. Avoid misting until fully cleared\n\n"
                f"Check top 2 inches of soil before watering your {label} going forward. 🌿"
            )
        elif "wilting" in scan_label and temp and temp > 35:
            reply = (
                f"Scan shows wilting + {temp}°C in {city} = **heat stress** (not a disease).\n\n"
                f"1. Move away from direct sun immediately\n"
                f"2. Water thoroughly if soil is dry\n"
                f"3. Mist leaves in the evening\n"
                f"4. Add gentle airflow (fan, not AC)\n\n"
                f"Your {label} should recover in 24-48 hours. 💧"
            )

    # ── Follow-up continuity ──────────────────────────────────────────────────
    if not reply:
        had_fungal  = any(w in prev_words for w in ["fungal", "fungus", "spotted", "spots", "mold"])
        getting_worse = any(w in message.lower() for w in ["worse", "spread", "still", "not improving", "not better"])
        if had_fungal and getting_worse:
            reply = (
                f"Since the fungal issue on your {label} is continuing:\n\n"
                f"1. Remove ALL affected leaves — even ones that look borderline\n"
                f"2. Switch to a copper-based systemic fungicide (stronger than neem oil)\n"
                f"3. Repot into fresh dry mix if roots smell musty\n"
                f"4. Keep humidity below 60% for at least 2 weeks\n\n"
                f"If new spots appear on healthy leaves within a week, isolate the plant."
            )

    # ── Standard intent responses ─────────────────────────────────────────────
    if not reply:

        if intent == "watering":
            if temp and temp > 35:
                reply = (
                    f"At {temp}°C in {city}, your {label} needs water more often than usual — "
                    f"heat speeds up transpiration significantly.\n\n{plant['watering']}"
                )
            elif hum and hum > 75:
                reply = (
                    f"With {hum}% humidity in {city}, soil stays moist longer. "
                    f"Always check the top inch before watering your {label} — "
                    f"overwatering in humidity causes root rot fast.\n\n{plant['watering']}"
                )
            else:
                reply = f"Watering guide for your {label}:\n\n{plant['watering']}"

        elif intent in ("disease", "diagnosis"):
            if scan_label:
                reply = (
                    f"The scan detected **{scan_label}** ({round(scan_conf*100)}% confidence) on your {label}.\n\n"
                    f"{plant['diseases']}\n\n"
                    f"{'Act on this — confidence is high.' if scan_conf > 0.8 else 'Monitor closely and treat early.'}"
                )
            else:
                syms = entities.get("symptoms", [])
                if syms:
                    reply = (
                        f"You mentioned {', '.join(syms)} on your {label}. "
                        f"The most likely causes:\n\n{plant['diseases']}\n\n"
                        f"Upload a photo for a scan — I can give a much more accurate diagnosis with one."
                    )
                else:
                    reply = (
                        f"Common issues to check on your {label}:\n\n{plant['diseases']}\n\n"
                        f"What specific symptoms are you seeing? Or upload a photo for a visual scan."
                    )

        elif intent == "sunlight":
            if uv and uv >= 8:
                reply = (
                    f"UV is {uv} in {city} — very high. Move your {label} away from direct sun today.\n\n"
                    f"{plant['sunlight']}"
                )
            else:
                reply = f"Sunlight guide for your {label}:\n\n{plant['sunlight']}"

        elif intent == "humidity":
            hum_ctx = f"Current humidity in {city} is {hum}%. " if hum else ""
            reply = f"{hum_ctx}{plant['humidity']}"

        elif intent == "temperature":
            temp_ctx = f"It's {temp}°C in {city}. " if temp else ""
            reply = f"{temp_ctx}Temperature guide for your {label}:\n\n{plant['temperature']}"

        elif intent == "fertiliser":
            reply = f"Fertilising guide for your {label}:\n\n{plant['fertiliser']}"

        elif intent == "pest":
            reply = f"Pest management for your {label}:\n\n{plant['pests']}\n\nIsolate affected plants immediately to stop spread."

        elif intent == "emergency":
            reply = (
                f"Let's act fast for your {label}!\n\n"
                f"Emergency signs: {plant['emergency']}\n\n"
                f"**Immediate checks:**\n"
                f"1. Soil wet + wilting → root rot — remove from pot, inspect roots\n"
                f"2. Soil bone dry + wilting → water immediately, move to shade\n"
                f"3. Black/mushy stem base → root rot — trim rot, repot in dry fresh mix\n"
                f"4. Cold limp leaves → frost/cold damage — move to warmth, no water for a week\n\n"
                f"Tell me exactly what you see and I'll give a precise plan."
            )

        elif intent == "travel":
            days = entities.get("days", 3)
            risk = ("HIGH" if (temp and temp > 32) or (hum and hum < 40)
                    else "MODERATE" if (temp and temp > 28) else "LOW")
            reply = (
                f"Travel risk for your {label} ({days} days): **{risk}**\n\n"
                f"1. Water thoroughly the morning you leave\n"
                f"2. Move to a cooler, shadier spot\n"
                f"3. For 5+ days: use self-watering spikes or ask someone to water\n"
                f"4. Group plants together for humidity microclimate\n"
                f"5. Remove flowers/buds to conserve energy"
            )

        elif intent == "repotting":
            reply = (
                f"Signs your {label} needs repotting: roots out of drainage holes, soil drying unusually fast.\n\n"
                f"1. Choose a pot only 2-3 cm wider — too big = waterlogging\n"
                f"2. Use fresh well-draining mix for your plant type\n"
                f"3. Water lightly after; keep from direct sun for 1 week\n"
                f"4. No fertiliser for 4-6 weeks — fresh soil has nutrients\n"
                f"5. Some leaf droop for a few days is normal transplant shock"
            )

        elif intent == "propagation":
            reply = (
                f"Propagating your {label}:\n\n"
                f"1. Take a cutting just below a node\n"
                f"2. Remove lower leaves — none should sit in water/soil\n"
                f"3. Place in water or moist perlite\n"
                f"4. Bright indirect light, 20-25°C, high humidity\n"
                f"5. Roots in 2-6 weeks — pot up when 3-5 cm long\n\n"
                f"Avoid propagating in winter — low light = slow or failed rooting."
            )

        elif intent == "recovery":
            reply = (
                f"Great that your {label} is improving! 🌱\n\n"
                f"1. Stick to your corrected watering schedule — no overcompensating\n"
                f"2. Don't move it — stability helps recovery\n"
                f"3. Hold fertiliser for 4-6 weeks — stressed roots can't absorb it\n"
                f"4. Remove dead leaves to redirect energy\n\n"
                f"New healthy growth should appear in 2-4 weeks."
            )

        else:  # care / general
            reply = (
                f"{greeting}I can help you take care of your {label}! Here's a quick overview:\n\n"
                f"💧 **Watering:** {plant['watering'][:120]}...\n"
                f"☀️ **Sunlight:** {plant['sunlight'][:100]}...\n"
                f"🌡️ **Temperature:** {plant['temperature'][:100]}...\n\n"
                f"What specific aspect would you like to know more about?"
            )

    return {
        "response": reply,
        "confidence": 0.72,
        "intent": intent,
        "suggestions": _generate_suggestions(intent, plant_name, weather),
        "severity": _estimate_severity(intent, scan, weather),
        "source": "rule_engine",
    }


def _humidity_tip(hum: float, label: str) -> str:
    if hum > 80:
        return f"the very high humidity could encourage fungal issues on {label}"
    if hum < 35:
        return f"the low humidity may cause dry tips on {label} — consider misting"
    return f"humidity is in a good range for {label}"


# =============================================================================
#  SHARED HELPERS
# =============================================================================

def _generate_suggestions(intent: str, plant_name: str, weather: dict) -> list:
    w = weather or {}
    base = [
        "How often should I water?",
        "What light does it need?",
        "Why are my leaves yellowing?",
        "How do I prevent root rot?",
    ]
    intent_map = {
        "watering":    ["Is my soil too wet?", "How much water at once?", "Should I water from below?"],
        "disease":     ["How do I treat root rot?", "Is this fungal or bacterial?", "Should I repot now?"],
        "pest":        ["How do I use neem oil?", "How fast do mites spread?", "Should I quarantine?"],
        "emergency":   ["Is this root rot?", "Should I repot now?", "How do I check roots?"],
        "sunlight":    ["What's the best window?", "Can it handle direct sun?", "Why are leaves bleaching?"],
        "repotting":   ["What soil mix?", "How big should the pot be?", "When is best to repot?"],
        "travel":      ["How long without water?", "Should I water heavily first?", "Self-watering spikes?"],
        "care":        ["How often should I water?", "What fertiliser should I use?", "Does it need repotting?"],
    }
    if intent in intent_map:
        return intent_map[intent]
    if w.get("temp", 25) > 33:
        base.insert(0, "How do I protect from heat?")
    if w.get("humidity", 60) > 80:
        base.insert(0, "Is high humidity causing disease?")
    return base[:4]


def _estimate_severity(intent: str, scan: dict, weather: dict) -> str:
    if intent == "emergency":
        return "critical"
    scan_label = (scan or {}).get("label", "").lower()
    scan_conf  = (scan or {}).get("confidence", 0)
    w = weather or {}
    if scan_conf > 0.8 and "fungal" in scan_label and w.get("humidity", 0) > 80:
        return "high"
    if intent in ("disease", "pest") and scan_conf > 0.6:
        return "moderate"
    if w.get("temp", 25) > 35 or w.get("temp", 25) < 10:
        return "moderate"
    return "low"