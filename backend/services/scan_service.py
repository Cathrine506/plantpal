import io
import os
import json
import base64
import numpy as np
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

PLANT_ID_API_KEY = os.getenv("PLANT_ID_API_KEY", "")

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import tensorflow as tf
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False

IMG_SIZE = (224, 224)
_model = None
_class_labels = []
_model_loaded = False

# Project root model/ (not backend/model/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "model"
MODEL_PATH = MODEL_DIR / "plant_model.h5"
LABELS_PATH = MODEL_DIR / "labels.json"
CLASS_NAMES_PATH = MODEL_DIR / "class_names.json"


def _labels_file() -> Path | None:
    if LABELS_PATH.exists():
        return LABELS_PATH
    if CLASS_NAMES_PATH.exists():
        return CLASS_NAMES_PATH
    return None


def _load_model():
    global _model, _class_labels, _model_loaded
    if _model_loaded:
        return
    _model_loaded = True
    if not TF_AVAILABLE:
        print("[scan] TensorFlow not installed — local model unavailable")
        return
    labels_file = _labels_file()
    try:
        if (
            MODEL_PATH.exists()
            and MODEL_PATH.stat().st_size > 0
            and labels_file
        ):
            _model = tf.keras.models.load_model(str(MODEL_PATH))
            with open(labels_file, encoding="utf-8") as f:
                _class_labels = json.load(f)
            print(f"[scan] Local model loaded ({len(_class_labels)} classes)")
        else:
            print(f"[scan] No trained model at {MODEL_PATH} (train with training/train_model.py)")
    except Exception as e:
        print(f"[scan] Could not load local model: {e}")


def _call_plant_id_api(image_bytes: bytes) -> dict | None:
    """Call Plant.id v3 for plant + disease identification."""
    if not PLANT_ID_API_KEY:
        return None
    try:
        b64 = base64.b64encode(image_bytes).decode()
        resp = requests.post(
            "https://api.plant.id/v3/identification",
            headers={"Api-Key": PLANT_ID_API_KEY, "Content-Type": "application/json"},
            json={
                "images": [b64],
                "classification_level": "species",
                "health": "all",
            },
            timeout=45,
        )
        if resp.status_code not in (200, 201):
            print(f"[scan] Plant.id HTTP {resp.status_code}: {resp.text[:300]}")
            return None

        data = resp.json()
        result = data.get("result") or {}
        suggestions = (result.get("classification") or {}).get("suggestions") or []
        if not suggestions:
            print("[scan] Plant.id returned no classification suggestions")
            return None

        plant = suggestions[0]
        disease_block = result.get("disease") or {}
        disease_suggestions = disease_block.get("suggestions") or []
        disease = disease_suggestions[0] if disease_suggestions else {}

        is_healthy = (result.get("is_healthy") or {}).get("binary", True)
        disease_name = disease.get("name", "Healthy" if is_healthy else "Unknown")
        disease_conf = float(disease.get("probability", 0.0))

        return {
            "label": disease_name,
            "confidence": round(disease_conf if disease_conf else plant.get("probability", 0.0), 4),
            "plant_name": plant.get("name", "Unknown"),
            "plant_confidence": round(float(plant.get("probability", 0.0)), 4),
            "disease": disease_name,
            "disease_confidence": round(disease_conf, 4),
            "is_healthy": bool(is_healthy),
            "simulated": False,
            "source": "plant_id_api",
        }
    except Exception as e:
        print(f"[scan] Plant.id API failed: {e}")
        return None


def _estimate_scan_severity(label: str, confidence: float) -> str:
    if label.lower() in ("healthy", "none"):
        return "none"
    if confidence > 0.8:
        return "high"
    if confidence > 0.6:
        return "moderate"
    return "low"


def _preprocess(img: "Image.Image") -> np.ndarray:
    img_rgb = img.resize(IMG_SIZE).convert("RGB")
    arr = np.array(img_rgb, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)


def predict_image(image_source) -> dict:
    if not PIL_AVAILABLE:
        return {"error": "Pillow not installed. Run: pip install Pillow"}

    try:
        img_bytes = (
            image_source if isinstance(image_source, bytes)
            else image_source.read()
        )
        img = Image.open(io.BytesIO(img_bytes))
    except Exception as e:
        return {"error": f"Could not open image: {e}"}

    # 1. Plant.id API
    api_result = _call_plant_id_api(img_bytes)
    if api_result:
        api_result["severity"] = _estimate_scan_severity(
            api_result["label"], api_result["confidence"]
        )
        return api_result

    # 2. Local trained model
    _load_model()
    if _model and _class_labels:
        arr = _preprocess(img)
        preds = _model.predict(arr, verbose=0)[0]
        top_idx = int(np.argmax(preds))
        top_conf = float(round(float(preds[top_idx]), 4))
        label = _class_labels[top_idx]
        all_scores = {
            _class_labels[i]: round(float(preds[i]), 4)
            for i in range(len(_class_labels))
        }
        return {
            "label": label,
            "confidence": top_conf,
            "all_scores": all_scores,
            "disease": label,
            "disease_confidence": top_conf,
            "simulated": False,
            "source": "local_model",
            "severity": _estimate_scan_severity(label, top_conf),
        }

    # 3. Nothing available
    hints = []
    if not PLANT_ID_API_KEY:
        hints.append("Set PLANT_ID_API_KEY in .env")
    if not MODEL_PATH.exists() or MODEL_PATH.stat().st_size == 0:
        hints.append("Train a local model: cd training && python train_model.py")
    return {
        "error": "Scan unavailable. " + " ".join(hints) if hints else "Scan unavailable.",
        "simulated": False,
    }


def predict_from_base64(b64_string: str) -> dict:
    try:
        img_bytes = base64.b64decode(b64_string)
        return predict_image(img_bytes)
    except Exception as e:
        return {"error": f"Invalid base64 image: {e}"}
