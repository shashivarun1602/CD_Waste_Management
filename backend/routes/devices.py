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
    if not device_service.collection("vehicles").find_one({"vehicle_id": data["vehicle_id"]}):
        return error("Vehicle not found", "VEHICLE_NOT_FOUND", 404)
    try:
        return success(device_service.create_device(data), "Device registered successfully", 201)
    except DuplicateKeyError:
        return error("Device already exists", "DUPLICATE_DEVICE", 409)


@devices_bp.put("/devices/<device_id>")
def update_device(device_id):
    if not device_service.get_device(device_id):
        return error("Device not found", "DEVICE_NOT_FOUND", 404)
    return success(device_service.update_device(device_id, request.get_json(silent=True) or {}), "Device updated successfully")


@devices_bp.delete("/devices/<device_id>")
def delete_device(device_id):
    if not device_service.get_device(device_id):
        return error("Device not found", "DEVICE_NOT_FOUND", 404)
    return success(device_service.deactivate_device(device_id), "Device deactivated successfully")