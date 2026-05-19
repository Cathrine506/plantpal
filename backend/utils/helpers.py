import re
import uuid
from datetime import datetime

def generate_session_id() -> str:
    return str(uuid.uuid4())

def validate_message(data: dict) -> tuple[bool, str]:
    message = data.get("message", "")
    if not message or not isinstance(message, str):
        return False, "message is required and must be a string"
    if len(message.strip()) == 0:
        return False, "message cannot be empty"
    if len(message) > 2000:
        return False, "message is too long (max 2000 characters)"
    return True, ""

def validate_weather(weather) -> dict | None:
    if not weather or not isinstance(weather, dict):
        return None
    cleaned = {}
    for key in ("temp", "humidity", "uvIndex", "cloudCover"):
        val = weather.get(key)
        if val is not None:
            try:
                cleaned[key] = float(val)
            except (TypeError, ValueError):
                pass
    city = weather.get("city")
    if city and isinstance(city, str):
        cleaned["city"] = city[:100]
    return cleaned if cleaned else None

def validate_scan(scan) -> dict | None:
    if not scan or not isinstance(scan, dict):
        return None
    label = scan.get("label")
    if not label:
        return None
    result = {"label": str(label)}
    conf = scan.get("confidence")
    if conf is not None:
        try:
            result["confidence"] = max(0.0, min(1.0, float(conf)))
        except (TypeError, ValueError):
            result["confidence"] = 0.5
    return result

def sanitize_string(s: str, max_len: int = 200) -> str:
    if not isinstance(s, str):
        return ""
    s = re.sub(r"[<>]", "", s)
    return s.strip()[:max_len]

def calculate_vitality_score(weather: dict) -> int:
    if not weather:
        return 65
    score = 100
    temp = weather.get("temp", 25)
    hum = weather.get("humidity", 60)
    uv = weather.get("uvIndex", 5)
    if temp > 38: score -= 30
    elif temp > 35: score -= 20
    elif temp > 32: score -= 10
    elif temp < 12: score -= 20
    elif temp < 16: score -= 8
    if hum > 85: score -= 15
    elif hum > 80: score -= 8
    elif hum < 30: score -= 15
    elif hum < 40: score -= 8
    if uv >= 10: score -= 15
    elif uv >= 8: score -= 8
    elif uv >= 6: score -= 3
    return max(0, min(100, score))
