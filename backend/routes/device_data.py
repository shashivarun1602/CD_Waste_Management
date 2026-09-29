from flask import Blueprint, request

from services import gps_service, weight_service
from services.device_auth import device_auth_error
from utils.response import error, success
from utils.validators import missing_fields, positive_number

device_data_bp = Blueprint("device_data", __name__)


@device_data_bp.post("/device/gps")
def device_gps():
    auth_error = device_auth_error()
    if auth_error:
        return error(*auth_error)

    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["device_id"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    gps_fix = data.get("gps_fix", True)
    if not isinstance(gps_fix, bool):
        return error("gps_fix must be a boolean", "INVALID_GPS_DATA")
    data["gps_fix"] = gps_fix

    if gps_fix:
        missing = missing_fields(data, ["latitude", "longitude"])
        if missing:
            return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
        try:
            latitude, longitude = float(data["latitude"]), float(data["longitude"])
        except (TypeError, ValueError):
            return error("latitude and longitude must be numbers", "INVALID_GPS_DATA")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            return error("latitude must be between -90 and 90 and longitude between -180 and 180", "INVALID_GPS_DATA")
        data.update({"latitude": latitude, "longitude": longitude})
    else:
        data["latitude"] = None
        data["longitude"] = None

    if data.get("satellites") is not None:
        try:
            satellites = int(data["satellites"])
        except (TypeError, ValueError):
            return error("satellites must be a non-negative integer", "INVALID_GPS_DATA")
        if satellites < 0 or str(satellites) != str(data["satellites"]):
            return error("satellites must be a non-negative integer", "INVALID_GPS_DATA")
        data["satellites"] = satellites

    data["source"] = "device"
    try:
        return success(gps_service.add_device_gps_point(data), "Device GPS recorded")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "DEVICE_DATA_REJECTED", 404 if isinstance(exc, LookupError) else 400)


@device_data_bp.post("/device/weight")
def device_weight():
    auth_error = device_auth_error()
    if auth_error:
        return error(*auth_error)

    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["device_id"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")

    raw_value = data.get("raw_value")
    weight_value = data.get("weight_kg")
    if raw_value is None and weight_value is None:
        return error("raw_value or weight_kg is required", "MISSING_FIELDS")

    if raw_value is not None:
        try:
            raw_number = int(raw_value)
        except (TypeError, ValueError):
            return error("raw_value must be an integer", "INVALID_RAW_WEIGHT")
        if isinstance(raw_value, bool) or str(raw_number) != str(raw_value):
            return error("raw_value must be an integer", "INVALID_RAW_WEIGHT")
        data["raw_value"] = raw_number
        data["calibration_status"] = str(data.get("calibration_status", "NOT_SET")).upper()
        if data["calibration_status"] not in {"NOT_SET", "SET"}:
            return error("calibration_status must be NOT_SET or SET", "INVALID_CALIBRATION_STATUS")

    if weight_value is not None:
        weight, message = positive_number(weight_value, "weight_kg")
        if message:
            return error(message, "INVALID_WEIGHT")
        if raw_value is not None and data["calibration_status"] != "SET":
            return error("weight_kg requires calibration_status SET", "INVALID_CALIBRATION_STATUS")
        data["weight_kg"] = weight

    if raw_value is not None and weight_value is None:
        data["weight_kg"] = None
        if data["calibration_status"] != "NOT_SET":
            return error("weight_kg is required when calibration_status is SET", "INVALID_CALIBRATION_STATUS")

    data["source"] = "device"
    try:
        return success(weight_service.add_device_weight(data), "Device weight recorded")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "DEVICE_DATA_REJECTED", 404 if isinstance(exc, LookupError) else 400)


@device_data_bp.get("/device/weight")
def device_weight_history():
    return success(weight_service.list_weight_readings(request.args.get("transport_id")), "Weight history loaded")