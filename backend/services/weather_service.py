import time
import requests
import os
from dotenv import load_dotenv

_cache: dict = {}
load_dotenv()
CACHE_TTL = int(os.getenv("WEATHER_CACHE_TTL", "600"))
OPENWEATHER_KEY = os.getenv("OPENWEATHER_API_KEY")

def _cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 2)},{round(lon, 2)}"

def get_weather(lat: float, lon: float) -> dict:
    key = _cache_key(lat, lon)
    cached = _cache.get(key)
    if cached and (time.time() - cached["ts"]) < CACHE_TTL:
        return cached["data"]

    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": OPENWEATHER_KEY, "units": "metric"},
            timeout=5
        )
        r.raise_for_status()
        d = r.json()

        cloud_cover = d.get("clouds", {}).get("all", 50)
        uv = 9 if cloud_cover < 10 else 7 if cloud_cover < 30 else 5 if cloud_cover < 60 else 2

        weather = {
            "temp": round(d["main"]["temp"]),
            "feels_like": round(d["main"]["feels_like"]),
            "humidity": d["main"]["humidity"],
            "uvIndex": uv,
            "cloudCover": cloud_cover,
            "city": d.get("name", "your area"),
            "description": d.get("weather", [{}])[0].get("description", ""),
            "wind_speed": d.get("wind", {}).get("speed", 0),
        }

        _cache[key] = {"data": weather, "ts": time.time()}
        return weather

    except Exception as e:
        print(f"[weather] Fetch failed: {e}")
        return _fallback_weather()

def _fallback_weather() -> dict:
    return {
        "temp": 26, "feels_like": 28, "humidity": 65,
        "uvIndex": 5, "cloudCover": 40, "city": "your area",
        "description": "partly cloudy", "wind_speed": 2,
    }

def assess_weather_risks(w: dict) -> list:
    risks = []
    temp = w.get("temp", 25)
    hum = w.get("humidity", 60)
    uv = w.get("uvIndex", 5)

    if temp > 38:
        risks.append({"level": "critical", "message": f"Extreme heat ({temp}°C) — severe stress risk for all plants"})
    elif temp > 35:
        risks.append({"level": "high", "message": f"Very hot ({temp}°C) — increase watering, move plants to shade"})
    elif temp > 32:
        risks.append({"level": "moderate", "message": f"Warm ({temp}°C) — monitor soil moisture frequently"})
    elif temp < 10:
        risks.append({"level": "high", "message": f"Cold ({temp}°C) — tropical plants at risk, protect from draughts"})
    elif temp < 15:
        risks.append({"level": "moderate", "message": f"Cool ({temp}°C) — slow growth period, reduce watering"})

    if hum > 85:
        risks.append({"level": "high", "message": f"Very high humidity ({hum}%) — elevated fungal disease risk"})
    elif hum > 75:
        risks.append({"level": "moderate", "message": f"High humidity ({hum}%) — reduce watering frequency"})
    elif hum < 30:
        risks.append({"level": "high", "message": f"Very dry air ({hum}%) — mist tropicals, watch for spider mites"})
    elif hum < 40:
        risks.append({"level": "moderate", "message": f"Low humidity ({hum}%) — consider misting or pebble trays"})

    if uv >= 10:
        risks.append({"level": "critical", "message": f"Extreme UV ({uv}) — move all light-sensitive plants from direct sun immediately"})
    elif uv >= 8:
        risks.append({"level": "high", "message": f"Very high UV ({uv}) — risk of sun scorch for plants in direct light"})

    return risks
