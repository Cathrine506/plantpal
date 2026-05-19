
import os
import json
import tensorflow as tf

from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.models import Model
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping

# =========================================================
# SETTINGS
# =========================================================

DATASET_DIR = "dataset"

MODEL_SAVE_PATH = "../model/plant_model.h5"
CLASS_NAMES_PATH = "../model/class_names.json"

IMG_SIZE = 224
BATCH_SIZE = 32
EPOCHS = 10

# =========================================================
# DATA GENERATORS
# =========================================================

train_datagen = ImageDataGenerator(
    rescale=1./255,
    validation_split=0.2,
    rotation_range=20,
    zoom_range=0.2,
    horizontal_flip=True,
)

train_generator = train_datagen.flow_from_directory(
    DATASET_DIR,
    target_size=(IMG_SIZE, IMG_SIZE),
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="training"
)

val_generator = train_datagen.flow_from_directory(
    DATASET_DIR,
    target_size=(IMG_SIZE, IMG_SIZE),
    batch_size=BATCH_SIZE,
    class_mode="categorical",
    subset="validation"
)

# =========================================================
# SAVE CLASS NAMES
# =========================================================

class_names = list(train_generator.class_indices.keys())

os.makedirs("../model", exist_ok=True)

with open(CLASS_NAMES_PATH, "w") as f:
    json.dump(class_names, f)

print("✅ Class names saved")

# =========================================================
# LOAD PRETRAINED MODEL
# =========================================================

base_model = MobileNetV2(
    weights="imagenet",
    include_top=False,
    input_shape=(IMG_SIZE, IMG_SIZE, 3)
)

base_model.trainable = False

# =========================================================
# BUILD MODEL
# =========================================================

x = base_model.output
x = GlobalAveragePooling2D()(x)
x = Dropout(0.3)(x)

predictions = Dense(
    train_generator.num_classes,
    activation="softmax"
)(x)

model = Model(
    inputs=base_model.input,
    outputs=predictions
)

# =========================================================
# COMPILE
# =========================================================

model.compile(
    optimizer="adam",
    loss="categorical_crossentropy",
    metrics=["accuracy"]
)

# =========================================================
# TRAIN
# =========================================================

early_stop = EarlyStopping(
    patience=3,
    restore_best_weights=True
)

history = model.fit(
    train_generator,
    validation_data=val_generator,
    epochs=EPOCHS,
    callbacks=[early_stop]
)

# =========================================================
# SAVE MODEL
# =========================================================

model.save(MODEL_SAVE_PATH)

print("✅ Model trained successfully!")
print(f"✅ Model saved to: {MODEL_SAVE_PATH}")
