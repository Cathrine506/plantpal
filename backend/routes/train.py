from flask import Blueprint, request, jsonify
from models.ml_model import start_training, get_training_status

train_bp = Blueprint("train", __name__)

@train_bp.route("/api/train", methods=["POST"])
def train():
    data = request.get_json(force=True, silent=True) or {}
    epochs = min(int(data.get("epochs", 10)), 100)
    batch_size = int(data.get("batch_size", 16))
    result = start_training(epochs=epochs, batch_size=batch_size)
    if "error" in result:
        return jsonify(result), 409
    return jsonify(result)

@train_bp.route("/api/train/status", methods=["GET"])
def training_status():
    return jsonify(get_training_status())
