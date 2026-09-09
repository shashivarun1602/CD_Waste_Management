from flask import Blueprint, request

from services import gps_service, weight_service
from utils.response import error, success
from utils.validators import missing_fields, positive_number

device_data_bp = Blueprint("device_data", __name__)


@device_data_bp.post("/device/gps")
def device_gps():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["device_id", "latitude", "longitude"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    try:
        latitude, longitude = float(data["latitude"]), float(data["longitude"])
    except (TypeError, ValueError):
        return error("latitude and longitude must be numbers", "INVALID_GPS_DATA")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return error("latitude must be between -90 and 90 and longitude between -180 and 180", "INVALID_GPS_DATA")
    data.update({"latitude": latitude, "longitude": longitude})
    try:
        return success(gps_service.add_device_gps_point(data), "Device GPS recorded")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "DEVICE_DATA_REJECTED", 404 if isinstance(exc, LookupError) else 400)


@device_data_bp.post("/device/weight")
def device_weight():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["device_id", "weight_kg"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    weight, message = positive_number(data.get("weight_kg"), "weight_kg")
    if message:
        return error(message, "INVALID_WEIGHT")
    data["weight_kg"] = weight
    try:
        return success(weight_service.add_device_weight(data), "Device weight recorded")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "DEVICE_DATA_REJECTED", 404 if isinstance(exc, LookupError) else 400)


@device_data_bp.get("/device/weight")
def device_weight_history():
    return success(weight_service.list_weight_readings(request.args.get("transport_id")), "Weight history loaded")