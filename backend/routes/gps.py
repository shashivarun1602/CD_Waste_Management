from flask import Blueprint, request

from services import gps_service
from utils.response import error, success
from utils.validators import missing_fields, positive_number, validate_source

gps_bp = Blueprint("gps", __name__)


@gps_bp.get("/gps")
def list_gps():
    return success(gps_service.list_gps_points(request.args.get("transport_id")), "GPS points loaded")


@gps_bp.post("/gps")
def add_gps():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["transport_id", "latitude", "longitude"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    try:
        data["latitude"] = float(data["latitude"])
        data["longitude"] = float(data["longitude"])
    except (TypeError, ValueError):
        return error("latitude and longitude must be numbers", "INVALID_GPS_DATA")
    if not -90 <= data["latitude"] <= 90 or not -180 <= data["longitude"] <= 180:
        return error("latitude must be between -90 and 90 and longitude between -180 and 180", "INVALID_GPS_DATA")
    if data.get("speed_kmph") is not None:
        value, message = positive_number(data["speed_kmph"], "speed_kmph")
        if message:
            return error(message, "INVALID_GPS_DATA")
        data["speed_kmph"] = value
    source_error = validate_source(data)
    if source_error:
        return error(source_error, "INVALID_SOURCE")
    return success(gps_service.add_gps_point(data), "GPS point recorded", 201)
