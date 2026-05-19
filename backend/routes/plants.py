from flask import Blueprint, jsonify
from services.plant_service import get_all_plants, PLANT_PROFILES

plants_bp = Blueprint("plants", __name__)

@plants_bp.route("/api/plants", methods=["GET"])
def list_plants():
    return jsonify(get_all_plants())

@plants_bp.route("/api/plants/<plant_key>", methods=["GET"])
def get_plant(plant_key):
    profile = PLANT_PROFILES.get(plant_key)
    if not profile:
        return jsonify({"error": f"Plant '{plant_key}' not found"}), 404
    return jsonify(profile)
