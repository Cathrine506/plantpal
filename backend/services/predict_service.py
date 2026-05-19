
import json
import numpy as np
from PIL import Image

from tensorflow.keras.models import load_model

MODEL_PATH = "model/plant_model.h5"
CLASS_PATH = "model/class_names.json"

model = load_model(MODEL_PATH)

with open(CLASS_PATH, "r") as f:
    class_names = json.load(f)

IMG_SIZE = 224

def predict_image(image_path):

    image = Image.open(image_path).convert("RGB")

    image = image.resize((IMG_SIZE, IMG_SIZE))

    image = np.array(image) / 255.0

    image = np.expand_dims(image, axis=0)

    predictions = model.predict(image)

    predicted_index = np.argmax(predictions)

    confidence = float(np.max(predictions))

    predicted_class = class_names[predicted_index]

    return {
        "class": predicted_class,
        "confidence": confidence
    }
