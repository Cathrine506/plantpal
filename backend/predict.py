
import os
from tensorflow.keras.models import load_model
import numpy as np
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "..",
    "model",
    "plant_model.h5"
)

model = load_model(MODEL_PATH)

CLASS_NAMES = [
    "Healthy",
    "Powdery Mildew",
    "Leaf Spot",
    "Rust"
]

def predict_image(image_path):
    img = Image.open(image_path).convert("RGB")
    img = img.resize((224, 224))

    img_array = np.array(img) / 255.0
    img_array = np.expand_dims(img_array, axis=0)

    prediction = model.predict(img_array)

    predicted_class = CLASS_NAMES[np.argmax(prediction)]
    confidence = float(np.max(prediction))

    return {
        "disease": predicted_class,
        "confidence": round(confidence * 100, 2)
    }
