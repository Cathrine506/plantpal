import os
import json
import threading
from pathlib import Path

TF_AVAILABLE = False
try:
    import tensorflow as tf
    from tensorflow.keras import layers, models
    from tensorflow.keras.preprocessing.image import ImageDataGenerator
    TF_AVAILABLE = True
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "model"
MODEL_PATH = MODEL_DIR / "plant_model.h5"
LABELS_PATH = MODEL_DIR / "labels.json"
TRAINING_DATA_DIR = PROJECT_ROOT / "training_data"

IMG_SIZE = (224, 224)
BATCH_SIZE = 16
EPOCHS = 30  # More epochs needed when training from scratch

train_status = {
    "running": False, "progress": 0, "epoch": 0,
    "total_epochs": EPOCHS, "message": "Idle",
    "error": None, "completed": False, "accuracy": None,
}


def get_training_status() -> dict:
    return dict(train_status)


def start_training(epochs: int = EPOCHS, batch_size: int = BATCH_SIZE) -> dict:
    global EPOCHS, BATCH_SIZE
    if train_status["running"]:
        return {"error": "Training already in progress"}
    if not TF_AVAILABLE:
        return {"error": "TensorFlow not installed"}
    if not TRAINING_DATA_DIR.exists():
        return {"error": f"Training data directory not found: {TRAINING_DATA_DIR}"}

    classes = [d for d in TRAINING_DATA_DIR.iterdir() if d.is_dir()]
    if len(classes) < 2:
        return {"error": "Need at least 2 class folders in training_data/"}

    # Check that at least some classes have images
    non_empty = [d for d in classes if any(d.iterdir())]
    if len(non_empty) < 2:
        return {"error": "At least 2 class folders must contain images. Add plant images first."}

    EPOCHS = epochs
    BATCH_SIZE = batch_size
    t = threading.Thread(target=_run_training, daemon=True)
    t.start()
    return {"message": f"Training started — {epochs} epochs, {batch_size} batch size (scratch CNN)"}


def _build_cnn(num_classes: int):
    base = tf.keras.applications.MobileNetV2(
        input_shape=(224, 224, 3),
        include_top=False,
        weights="imagenet"   # ← pre-trained on 1.2M images
    )
    base.trainable = False   # freeze base initially

    model = tf.keras.Sequential([
        base,
        tf.keras.layers.GlobalAveragePooling2D(),
        tf.keras.layers.Dropout(0.3),
        tf.keras.layers.Dense(128, activation="relu"),
        tf.keras.layers.Dense(num_classes, activation="softmax"),
    ])

    model.compile(
        optimizer=tf.keras.optimizers.Adam(1e-4),
        loss="categorical_crossentropy",
        metrics=["accuracy"],
    )
    return model


def _run_training():
    global train_status
    train_status.update({
        "running": True, "progress": 0, "epoch": 0,
        "message": "Preparing dataset...",
        "error": None, "completed": False, "accuracy": None,
    })
    try:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)

        # ── Data augmentation ─────────────────────────────────────
        # rescale=1./255 normalises pixel values to [0, 1].
        # Strong augmentation helps the scratch CNN generalise better.
        aug = ImageDataGenerator(
            rescale=1.0 / 255,
            validation_split=0.2,
            rotation_range=40,
            zoom_range=0.3,
            horizontal_flip=True,
            vertical_flip=True,
            width_shift_range=0.2,
            height_shift_range=0.2,
            shear_range=0.2,
            brightness_range=[0.7, 1.3],
            fill_mode="nearest",
        )

        train_gen = aug.flow_from_directory(
            str(TRAINING_DATA_DIR),
            target_size=IMG_SIZE,
            batch_size=BATCH_SIZE,
            class_mode="categorical",
            subset="training",
        )
        val_gen = aug.flow_from_directory(
            str(TRAINING_DATA_DIR),
            target_size=IMG_SIZE,
            batch_size=BATCH_SIZE,
            class_mode="categorical",
            subset="validation",
        )

        class_labels = list(train_gen.class_indices.keys())
        num_classes = len(class_labels)
        train_status["message"] = (
            f"Building scratch CNN for {num_classes} classes: {class_labels}"
        )

        model = _build_cnn(num_classes)

        total_epochs = EPOCHS

        class ProgressCallback(tf.keras.callbacks.Callback):
            def on_epoch_end(self, epoch, logs=None):
                acc = logs.get("val_accuracy", logs.get("accuracy", 0))
                train_status.update({
                    "epoch": epoch + 1,
                    "total_epochs": total_epochs,
                    "progress": round((epoch + 1) / total_epochs * 80),
                    "message": f"Epoch {epoch+1}/{total_epochs} — val_acc: {acc:.3f}",
                    "accuracy": round(float(acc), 4),
                })

        # ── Early stopping ────────────────────────────────────────
        # Stops training if val_accuracy doesn't improve for 5 epochs
        # and restores the best weights automatically.
        early_stop = tf.keras.callbacks.EarlyStopping(
            monitor="val_accuracy",
            patience=5,
            restore_best_weights=True,
            verbose=0,
        )

        # ── Reduce LR on plateau ──────────────────────────────────
        # Halves the learning rate if val_loss stalls for 3 epochs.
        reduce_lr = tf.keras.callbacks.ReduceLROnPlateau(
            monitor="val_loss",
            factor=0.5,
            patience=3,
            min_lr=1e-6,
            verbose=0,
        )

        model.fit(
            train_gen,
            validation_data=val_gen,
            epochs=total_epochs,
            callbacks=[ProgressCallback(), early_stop, reduce_lr],
            verbose=0,
        )

        train_status["message"] = "Saving model..."
        model.save(str(MODEL_PATH))
        with open(LABELS_PATH, "w") as f:
            json.dump(class_labels, f)

        train_status.update({
            "running": False,
            "progress": 100,
            "completed": True,
            "message": f"Training complete! Classes: {class_labels}",
        })

    except Exception as e:
        train_status.update({
            "running": False,
            "error": str(e),
            "message": f"Training failed: {e}",
            "completed": False,
        })
