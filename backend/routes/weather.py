from flask import Blueprint, request, jsonify
from services.weather_service import get_weather, assess_weather_risks
from database.db import save_weather
from utils.helpers import calculate_vitality_score

weather_bp = Blueprint("weather", __name__)

@weather_bp.route("/api/weather", methods=["GET"])
def weather():
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))
    except (TypeError, ValueError):
        return jsonify({"error": "lat and lon must be valid numbers"}), 400

    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return jsonify({"error": "lat/lon out of valid range"}), 400

    data = get_weather(lat, lon)
    data["vitality_score"] = calculate_vitality_score(data)
    data["risks"] = assess_weather_risks(data)

    save_weather(lat, lon, data)
    return jsonify(data)
