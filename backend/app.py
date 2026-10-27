from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pymongo.errors import ServerSelectionTimeoutError
from werkzeug.exceptions import HTTPException

from config import Config
from db import get_database, init_db
from routes.dashboard import dashboard_bp
from routes.device_data import device_data_bp
from routes.devices import devices_bp
from routes.drivers import drivers_bp
from routes.facilities import facilities_bp
from routes.gps import gps_bp
from routes.sites import sites_bp
from routes.transport import transport_bp
from routes.vehicles import vehicles_bp
from routes.waste import waste_bp
from services.common import collection, now

ROOT_DIR = Path(__file__).resolve().parent.parent

app = Flask(__name__, static_folder=str(ROOT_DIR / "public"), static_url_path="")
app.config.from_object(Config)
if Config.CORS_ORIGINS:
    CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS}})
init_db()

DEVICE_API_PREFIX = "/api/device/"

for blueprint in (
    sites_bp,
    vehicles_bp,
    drivers_bp,
    facilities_bp,
    waste_bp,
    transport_bp,
    gps_bp,
    dashboard_bp,
    devices_bp,
    device_data_bp,
):
    app.register_blueprint(blueprint, url_prefix="/api")


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/health")
@app.get("/api/health")
def health():
    return jsonify({"success": True, "message": "API is healthy", "data": {"status": "ok"}})


@app.get("/api/health/ready")
def readiness():
    try:
        get_database().command("ping")
    except Exception:
        return jsonify({
            "success": False,
            "message": "Database is unavailable. Check the MongoDB Atlas cluster and network access.",
            "error": "DATABASE_UNAVAILABLE",
        }), 503
    return jsonify({"success": True, "message": "Database is reachable", "data": {"status": "ready"}})


@app.after_request
def audit_mutation(response):
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return response
    if not request.path.startswith("/api/") or request.path.startswith(DEVICE_API_PREFIX):
        return response
    if response.status_code in {401, 503}:
        return response
    try:
        collection("audit_log").insert_one({
            "actor": "anonymous",
            "method": request.method,
            "path": request.path,
            "status_code": response.status_code,
            "success": response.status_code < 400,
            "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
            "user_agent": request.headers.get("User-Agent"),
            "timestamp": now(),
        })
    except Exception:
        app.logger.warning("Audit log write failed")
    return response


@app.after_request
def security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


@app.errorhandler(404)
def not_found(error):
    return jsonify({"success": False, "message": "Resource not found", "error": "NOT_FOUND"}), 404


@app.errorhandler(HTTPException)
def handle_http_error(error):
    code = error.name.upper().replace(" ", "_")
    return jsonify({"success": False, "message": error.description, "error": code}), error.code


@app.errorhandler(ServerSelectionTimeoutError)
def database_unavailable(error):
    app.logger.warning("Database unavailable: %s", error)
    return jsonify({
        "success": False,
        "message": "Database is unavailable. Check the MongoDB Atlas cluster and network access.",
        "error": "DATABASE_UNAVAILABLE",
    }), 503


@app.errorhandler(Exception)
def handle_error(error):
    app.logger.exception("Unhandled application error")
    return jsonify({"success": False, "message": "Internal server error", "error": "INTERNAL_ERROR"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, debug=Config.DEBUG)
