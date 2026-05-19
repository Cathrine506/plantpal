"""Production entry point for gunicorn on Render."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv

load_dotenv()

from database.db import init_db
from app import create_app

init_db()
app = create_app()
