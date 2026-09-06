from flask import Blueprint, request

from services import vehicle_service
from services.transport_service import vehicle_history
from utils.response import error, success
from utils.validators import missing_fields

vehicles_bp = Blueprint("vehicles", __name__)


@vehicles_bp.get("/vehicles")
def list_vehicles():
    return success(vehicle_service.list_vehicles(), "Vehicles loaded")


@vehicles_bp.get("/vehicles/<vehicle_id>")
def get_vehicle(vehicle_id):
    vehicle = vehicle_service.get_vehicle(vehicle_id)
    return success(vehicle, "Vehicle loaded") if vehicle else error("Vehicle not found", "VEHICLE_NOT_FOUND", 404)


@vehicles_bp.get("/vehicles/<vehicle_id>/history")
def get_vehicle_history(vehicle_id):
    if not vehicle_service.get_vehicle(vehicle_id):
        return error("Vehicle not found", "VEHICLE_NOT_FOUND", 404)
    return success(vehicle_history(vehicle_id), "Vehicle history loaded")


@vehicles_bp.post("/vehicles")
def create_vehicle():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["registration_number", "vehicle_type", "capacity_kg"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    try:
        return success(vehicle_service.create_vehicle(data), "Vehicle created successfully", 201)
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            return error("Registration number already exists", "DUPLICATE_REGISTRATION", 409)
        raise


@vehicles_bp.put("/vehicles/<vehicle_id>")
def update_vehicle(vehicle_id):
    if not vehicle_service.get_vehicle(vehicle_id):
        return error("Vehicle not found", "VEHICLE_NOT_FOUND", 404)
    return success(vehicle_service.update_vehicle(vehicle_id, request.get_json(silent=True) or {}), "Vehicle updated successfully")


@vehicles_bp.delete("/vehicles/<vehicle_id>")
def delete_vehicle(vehicle_id):
    if not vehicle_service.get_vehicle(vehicle_id):
        return error("Vehicle not found", "VEHICLE_NOT_FOUND", 404)
    return success(vehicle_service.deactivate_vehicle(vehicle_id), "Vehicle deactivated successfully")
