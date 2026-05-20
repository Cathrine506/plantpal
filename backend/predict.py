"""
Legacy predict helper — do not load the model at import time.
Use services.scan_service.predict_image instead.
"""

from services.scan_service import predict_image

__all__ = ["predict_image"]
