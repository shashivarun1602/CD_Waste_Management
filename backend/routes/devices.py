from flask import Blueprint, request
from pymongo.errors import DuplicateKeyError

from services import device_service
from utils.response import error, success
from utils.validators import missing_fields

devices_bp = Blueprint("devices", __name__)


@devices_bp.get("/devices")
def list_devices():
    return success(device_service.list_devices(), "Devices loaded")


@devices_bp.get("/devices/<device_id>")
def get_device(device_id):
    device = device_service.get_device(device_id)
    return success(device, "Device loaded") if device else error("Device not found", "DEVICE_NOT_FOUND", 404)


@devices_bp.post("/devices")
def create_device():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["vehicle_id"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    if data.get("device_id") is not None and (not isinstance(data["device_id"], str) or not data["device_id"].strip()):
        return error("device_id must be a non-empty string", "INVALID_DEVICE_ID")
    if not device_service.collection("vehicles").find_one({"vehicle_id": data["vehicle_id"]}):
        return error("Vehicle not found", "VEHICLE_NOT_FOUND", 404)
    try:
        return success(device_service.create_device(data), "Device registered successfully", 201)
    except DuplicateKeyError:
        return error("Device already exists", "DUPLICATE_DEVICE", 409)
    except LookupError as exc:
        return error(str(exc), "VEHICLE_NOT_FOUND", 404)
    except RuntimeError as exc:
        return error(str(exc), "DEVICE_VEHICLE_CONFLICT", 409)
    except ValueError as exc:
        return error(str(exc), "INVALID_DEVICE_ASSIGNMENT")


@devices_bp.put("/devices/<device_id>")
def update_device(device_id):
    if not device_service.get_device(device_id):
        return error("Device not found", "DEVICE_NOT_FOUND", 404)
    try:
        return success(device_service.update_device(device_id, request.get_json(silent=True) or {}), "Device updated successfully")
    except LookupError as exc:
        return error(str(exc), "VEHICLE_NOT_FOUND", 404)
    except RuntimeError as exc:
        return error(str(exc), "DEVICE_VEHICLE_CONFLICT", 409)
    except ValueError as exc:
        return error(str(exc), "INVALID_DEVICE_UPDATE")


@devices_bp.delete("/devices/<device_id>")
def delete_device(device_id):
    if not device_service.get_device(device_id):
        return error("Device not found", "DEVICE_NOT_FOUND", 404)
    return success(device_service.deactivate_device(device_id), "Device deactivated successfully")