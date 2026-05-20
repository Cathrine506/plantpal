"""
PlantPal — Production Flask Backend
=====================================
Run:  python app.py
Open: http://localhost:5000
"""

import os
import sys
from predict import predict_image

# Add backend directory to path so imports work
sys.path.insert(0, os.path.dirname(__file__))

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from database.db import init_db
from routes.chat import chat_bp
from routes.scan import scan_bp
from routes.weather import weather_bp
from routes.plants import plants_bp
from routes.train import train_bp

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

def create_app() -> Flask:
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "plantpal-secret-2024")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max upload

    CORS(app, origins=CORS_ORIGINS)

    app.register_blueprint(chat_bp)
    app.register_blueprint(scan_bp)
    app.register_blueprint(weather_bp)
    app.register_blueprint(plants_bp)
    app.register_blueprint(train_bp)

    @app.route("/")
    def index():
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/<path:filename>")
    def static_files(filename):
        try:
            return send_from_directory(FRONTEND_DIR, filename)
        except Exception:
            return send_from_directory(FRONTEND_DIR, "index.html")

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": "3.0.0"})

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large (max 16 MB)"}), 413

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": "Internal server error"}), 500

    @app.route("/predict", methods=["POST"])
    def predict():
        file = request.files["image"]

        filepath = "temp.jpg"
        file.save(filepath)

        result = predict_image(filepath)

        return jsonify(result)



    return app

if __name__ == "__main__":
    init_db()

    print("\n" + "=" * 60)
    print("  PlantPal v3.0 - AI Plant Health Assistant")
    print("=" * 60)
    print(f"  Frontend : {FRONTEND_DIR}")
    print(f"  Debug    : {DEBUG}")
    print(f"  AI Mode  : {'OpenAI GPT' if os.getenv('OPENAI_API_KEY') else 'Rule Engine (set OPENAI_API_KEY for GPT)'}")
    print("=" * 60)
    print("  Endpoints:")
    print("  GET  /                 -> Home page")
    print("  POST /api/chat         -> AI chatbot")
    print("  POST /api/scan         -> Disease prediction")
    print("  GET  /api/weather      -> Weather proxy")
    print("  GET  /api/plants       -> Plant list")
    print("  POST /api/train        -> Retrain model")
    print("  GET  /api/train/status -> Training progress")
    print("=" * 60)
    print(f"\n  Open: http://localhost:{PORT}\n")

    app = create_app()
    app.run(debug=DEBUG, host="0.0.0.0", port=PORT, use_reloader=False)
