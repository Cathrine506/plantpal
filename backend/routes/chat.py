from flask import Blueprint, request, jsonify
from services.ai_service import chat_with_ai
from database.db import save_message, get_history
from utils.helpers import validate_message, validate_weather, validate_scan, sanitize_string

chat_bp = Blueprint("chat", __name__)

@chat_bp.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}

    valid, err = validate_message(data)
    if not valid:
        return jsonify({"error": err}), 400

    message      = data["message"].strip()
    session_id   = sanitize_string(data.get("session_id", "default"), 64) or "default"
    plant_name   = sanitize_string(data.get("plant_name", ""), 100)
    weather      = validate_weather(data.get("weather"))
    scan         = validate_scan(data.get("scan_result"))

    # Load history from DB if frontend didn't send it
    sent_history = data.get("conversation_history") or data.get("history") or []
    if sent_history and isinstance(sent_history, list):
        history = [
            h for h in sent_history[-20:]
            if isinstance(h, dict) and h.get("role") in ("user", "assistant")
        ]
    else:
        history = get_history(session_id, limit=20)

    result = chat_with_ai(message, history, weather, scan, plant_name)

    save_message(session_id, "user", message, result.get("intent"))
    save_message(session_id, "assistant", result["response"])

    return jsonify({
        "response":    result["response"],
        "confidence":  result.get("confidence", 0.75),
        "intent":      result.get("intent", "general_care"),
        "suggestions": result.get("suggestions", []),
        "severity":    result.get("severity", "low"),
        "source":      result.get("source", "rule_engine"),
    })
