from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

from config import Config
from db import init_db
from routes.dashboard import dashboard_bp
from routes.drivers import drivers_bp
from routes.facilities import facilities_bp
from routes.gps import gps_bp
from routes.sites import sites_bp
from routes.transport import transport_bp
from routes.vehicles import vehicles_bp
from routes.waste import waste_bp

ROOT_DIR = Path(__file__).resolve().parent.parent

app = Flask(__name__, static_folder=str(ROOT_DIR / "frontend"), static_url_path="")
app.config.from_object(Config)
CORS(app)
init_db()

for blueprint in (
    sites_bp,
    vehicles_bp,
    drivers_bp,
    facilities_bp,
    waste_bp,
    transport_bp,
    gps_bp,
    dashboard_bp,
):
    app.register_blueprint(blueprint, url_prefix="/api")


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/health")
def health():
    return jsonify({"success": True, "message": "API is healthy", "data": {"status": "ok"}})


@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "message": "Resource not found", "error": "NOT_FOUND"}), 404


@app.errorhandler(Exception)
def handle_error(error):
    app.logger.exception("Unhandled application error")
    return jsonify({"success": False, "message": "Internal server error", "error": "INTERNAL_ERROR"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
