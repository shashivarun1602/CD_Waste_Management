"""Vercel entrypoint that exposes the existing Flask application."""

import importlib.util
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

spec = importlib.util.spec_from_file_location("cd_waste_application", BACKEND_DIR / "app.py")
application_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(application_module)

app = application_module.app
