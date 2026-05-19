import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "plantpal-dev-secret-2024")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
    DATABASE_PATH = os.getenv("DATABASE_PATH", "database/plantpal.db")
    WEATHER_CACHE_TTL = int(os.getenv("WEATHER_CACHE_TTL", "600"))  # 10 minutes
    MODEL_PATH = os.getenv("MODEL_PATH", "../model/plant_model.h5")
    LABELS_PATH = os.getenv("LABELS_PATH", "../model/labels.json")
    TRAINING_DATA_DIR = os.getenv("TRAINING_DATA_DIR", "../training_data")
    IMG_SIZE = (224, 224)
    BATCH_SIZE = 16
    EPOCHS = 10
    MAX_HISTORY_LENGTH = 20
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"
    PORT = int(os.getenv("PORT", "5000"))
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
