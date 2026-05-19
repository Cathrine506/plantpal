from flask import Blueprint, request, jsonify
from services.scan_service import predict_image, predict_from_base64
from services.weather_service import assess_weather_risks
from database.db import save_scan
from utils.helpers import validate_weather, sanitize_string

scan_bp = Blueprint("scan", __name__)

@scan_bp.route("/api/scan", methods=["POST"])
def scan():
    session_id = sanitize_string(request.form.get("session_id", "default"), 64) or "default"
    weather = validate_weather(
        request.form.get("weather") and __import__("json").loads(request.form.get("weather", "{}"))
        if request.content_type and "multipart" in request.content_type else
        (request.get_json(silent=True) or {}).get("weather")
    )

    if "image" in request.files:
        file = request.files["image"]
        result = predict_image(file.read())
    elif request.is_json:
        body = request.get_json()
        b64 = body.get("image_base64", "")
        weather = validate_weather(body.get("weather"))
        session_id = sanitize_string(body.get("session_id", "default"), 64)
        if not b64:
            return jsonify({"error": "Provide image as multipart 'image' or JSON 'image_base64'"}), 400
        result = predict_from_base64(b64)
    else:
        return jsonify({"error": "Provide image as multipart 'image' field or JSON 'image_base64'"}), 400

    if "error" in result:
        return jsonify(result), 422

    # Build diagnosis narrative
    label = result.get("disease") or result["label"]
    conf = result.get("disease_confidence") or result["confidence"]
    diagnosis = _build_diagnosis(label, conf, weather, result)
    result["diagnosis"] = diagnosis

    # Generate weather-context risks
    if weather:
        result["weather_risks"] = assess_weather_risks(weather)
        result["multi_modal"] = _multi_modal_note(label, conf, weather)

    save_scan(session_id, label, conf, weather, diagnosis)
    return jsonify(result)

def _build_diagnosis(label: str, confidence: float, weather: dict, result: dict | None = None) -> str:
    w = weather or {}
    hum = w.get("humidity")
    temp = w.get("temp")
    uv = w.get("uvIndex")
    city = w.get("city", "your area")
    conf_pct = round(confidence * 100)
    result = result or {}
    plant_line = ""
    if result.get("plant_name") and result.get("source") == "plant_id_api":
        plant_pct = round((result.get("plant_confidence") or 0) * 100)
        plant_line = f" Plant identified as {result['plant_name']} ({plant_pct}% match)."

    if label.lower() in ("healthy", "none") or result.get("is_healthy"):
        cond = f" Conditions in {city}: {temp}°C, {hum}% humidity." if weather else ""
        return f"Your plant appears healthy ({conf_pct}% confidence).{plant_line}{cond} Continue your current care routine and scan again in 7 days."

    if label == "Fungal":
        env = f" The current {hum}% humidity in {city} is significantly increasing the risk." if hum and hum > 70 else ""
        return (f"Fungal infection detected ({conf_pct}% confidence).{env} "
                f"Remove affected leaves, improve airflow, reduce watering, and apply neem oil or copper-based fungicide.")

    if label == "Wilting":
        env = f" At {temp}°C in {city}, heat stress is the most likely cause." if temp and temp > 32 else ""
        return (f"Wilting detected ({conf_pct}% confidence).{env} "
                f"Check soil moisture — if dry, water immediately and move to shade. "
                f"If soil is wet, suspect root rot and check roots.")

    if label == "Scorch":
        env = f" UV Index is {uv} in {city} — very high." if uv and uv >= 8 else ""
        return (f"Leaf scorch detected ({conf_pct}% confidence).{env} "
                f"Move the plant away from direct sun, water in the morning, "
                f"and consider a sheer curtain to filter harsh light.")

    return (
        f"{label} detected ({conf_pct}% confidence).{plant_line} "
        f"Please consult the chatbot for personalised recovery advice."
    )

def _multi_modal_note(label: str, conf: float, weather: dict) -> str | None:
    w = weather or {}
    hum = w.get("humidity", 0)
    temp = w.get("temp", 25)
    uv = w.get("uvIndex", 5)
    if label == "Fungal" and hum > 80:
        return f"HIGH CONFIDENCE: Fungal detection + {hum}% humidity = strong fungal stress indicator. Act immediately."
    if label == "Wilting" and temp > 35:
        return f"HIGH CONFIDENCE: Wilting + {temp}°C heat = heat stress. Move to shade and water now."
    if label == "Scorch" and uv >= 8:
        return f"HIGH CONFIDENCE: Scorch + UV {uv} = sun damage confirmed. Relocate plant immediately."
    return None
