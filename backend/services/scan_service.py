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
_model_load_failed = False

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


def _model_available() -> bool:
    return MODEL_PATH.exists() and MODEL_PATH.stat().st_size > 0 and _labels_file() is not None


def _load_model() -> bool:
    """Load plant_model.h5 once. Returns True if ready for inference."""
    global _model, _class_labels, _model_loaded, _model_load_failed
    if _model is not None:
        return True
    if _model_load_failed:
        return False
    if _model_loaded:
        return _model is not None
    _model_loaded = True

    if not TF_AVAILABLE:
        print("[scan] TensorFlow not installed — will try Plant.id fallback")
        return False
    if not _model_available():
        print(f"[scan] No trained model at {MODEL_PATH}")
        return False

    labels_file = _labels_file()
    try:
        _model = tf.keras.models.load_model(str(MODEL_PATH), compile=False)
        with open(labels_file, encoding="utf-8") as f:
            _class_labels = json.load(f)
        print(f"[scan] Local model loaded ({len(_class_labels)} classes)")
        return True
    except Exception as e:
        _model_load_failed = True
        print(f"[scan] Could not load local model: {e}")
        return False


def _predict_local(img: "Image.Image") -> dict | None:
    """Run trained MobileNetV2 model. Returns None if unavailable or inference fails."""
    if not _load_model():
        return None
    try:
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
    except Exception as e:
        print(f"[scan] Local prediction failed: {e}")
        return None


def _call_plant_id_api(image_bytes: bytes) -> dict | None:
    """Plant.id fallback when local model is missing or fails."""
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
    name = label.lower()
    if "healthy" in name or name in ("healthy", "none"):
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

    # 1. Your trained model (primary)
    local_result = _predict_local(img)
    if local_result:
        return local_result

    # 2. Plant.id API (fallback)
    api_result = _call_plant_id_api(img_bytes)
    if api_result:
        api_result["severity"] = _estimate_scan_severity(
            api_result["label"], api_result["confidence"]
        )
        api_result["fallback"] = True
        return api_result

    # 3. Nothing worked
    hints = []
    if not _model_available():
        hints.append("Train local model: cd training && python train_model.py")
    elif not TF_AVAILABLE:
        hints.append("Install TensorFlow for local model, or set PLANT_ID_API_KEY for fallback")
    if not PLANT_ID_API_KEY:
        hints.append("Set PLANT_ID_API_KEY in .env for API fallback")
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
