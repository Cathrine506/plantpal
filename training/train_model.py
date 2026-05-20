
import os
import json
import tensorflow as tf

from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.models import Model
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, CSVLogger

# =========================================================
# SETTINGS
# =========================================================

DATASET_DIR = "dataset"

MODEL_DIR = os.path.join("..", "model")
MODEL_SAVE_PATH = os.path.join(MODEL_DIR, "plant_model.h5")
CLASS_NAMES_PATH = os.path.join(MODEL_DIR, "class_names.json")
HISTORY_PATH = os.path.join(MODEL_DIR, "training_history.csv")

IMG_SIZE = 224
BATCH_SIZE = 16  # lower = less RAM (use 8 if it still crashes)
EPOCHS = 10

# Limit TensorFlow thread/memory pressure on laptops
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
try:
    gpus = tf.config.list_physical_devices("GPU")
    for gpu in gpus:
        tf.config.experimental.set_memory_growth(gpu, True)
except Exception:
    pass


def main():
    if not os.path.isdir(DATASET_DIR):
        print(f"[error] Missing folder: {os.path.abspath(DATASET_DIR)}")
        return

    os.makedirs(MODEL_DIR, exist_ok=True)

    train_datagen = ImageDataGenerator(
        rescale=1.0 / 255,
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
        subset="training",
        shuffle=True,
    )

    val_generator = train_datagen.flow_from_directory(
        DATASET_DIR,
        target_size=(IMG_SIZE, IMG_SIZE),
        batch_size=BATCH_SIZE,
        class_mode="categorical",
        subset="validation",
        shuffle=False,
    )

    class_names = list(train_generator.class_indices.keys())
    with open(CLASS_NAMES_PATH, "w", encoding="utf-8") as f:
        json.dump(class_names, f)
    print(f"[ok] Class names saved ({len(class_names)} classes)")

    base_model = MobileNetV2(
        weights="imagenet",
        include_top=False,
        input_shape=(IMG_SIZE, IMG_SIZE, 3),
    )
    base_model.trainable = False

    x = base_model.output
    x = GlobalAveragePooling2D()(x)
    x = Dropout(0.3)(x)
    predictions = Dense(train_generator.num_classes, activation="softmax")(x)
    model = Model(inputs=base_model.input, outputs=predictions)

    model.compile(
        optimizer="adam",
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )

    # Saves best model DURING training (so a crash at epoch 8 still keeps progress)
    checkpoint = ModelCheckpoint(
        MODEL_SAVE_PATH,
        monitor="val_accuracy",
        save_best_only=True,
        mode="max",
        verbose=1,
    )
    early_stop = EarlyStopping(
        monitor="val_accuracy",
        patience=3,
        restore_best_weights=True,
        mode="max",
        verbose=1,
    )
    csv_log = CSVLogger(HISTORY_PATH, append=False)

    print(f"[train] Starting: {EPOCHS} epochs, batch_size={BATCH_SIZE}")
    print(f"[train] Best model will be saved to: {os.path.abspath(MODEL_SAVE_PATH)}")
    print("[train] Do not close this window until you see 'Training complete'")

    try:
        history = model.fit(
            train_generator,
            validation_data=val_generator,
            epochs=EPOCHS,
            callbacks=[checkpoint, early_stop, csv_log],
        )
    except KeyboardInterrupt:
        print("\n[warn] Training interrupted by user.")
        model.save(MODEL_SAVE_PATH)
        print(f"[ok] Saved current weights to {MODEL_SAVE_PATH}")
        return

    # Final save (best weights already saved by checkpoint; this ensures file exists)
    model.save(MODEL_SAVE_PATH)

    final_acc = max(history.history.get("val_accuracy", [0]))
    print("[ok] Training complete!")
    print(f"[ok] Best validation accuracy: {final_acc:.4f}")
    print(f"[ok] Model saved to: {os.path.abspath(MODEL_SAVE_PATH)}")
    print(f"[ok] History saved to: {os.path.abspath(HISTORY_PATH)}")

    size_mb = os.path.getsize(MODEL_SAVE_PATH) / (1024 * 1024)
    if size_mb < 1:
        print("[error] Model file is too small — training may have failed.")
    else:
        print(f"[ok] Model file size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
