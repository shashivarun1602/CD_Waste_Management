from flask import Blueprint, request

from services import driver_service
from utils.response import error, success
from utils.validators import missing_fields

drivers_bp = Blueprint("drivers", __name__)


@drivers_bp.get("/drivers")
def list_drivers():
    return success(driver_service.list_drivers(), "Drivers loaded")


@drivers_bp.get("/drivers/<driver_id>")
def get_driver(driver_id):
    driver = driver_service.get_driver(driver_id)
    return success(driver, "Driver loaded") if driver else error("Driver not found", "DRIVER_NOT_FOUND", 404)


@drivers_bp.post("/drivers")
def create_driver():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["name", "license_number"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    return success(driver_service.create_driver(data), "Driver created successfully", 201)


@drivers_bp.put("/drivers/<driver_id>")
def update_driver(driver_id):
    if not driver_service.get_driver(driver_id):
        return error("Driver not found", "DRIVER_NOT_FOUND", 404)
    return success(driver_service.update_driver(driver_id, request.get_json(silent=True) or {}), "Driver updated successfully")


@drivers_bp.delete("/drivers/<driver_id>")
def delete_driver(driver_id):
    if not driver_service.get_driver(driver_id):
        return error("Driver not found", "DRIVER_NOT_FOUND", 404)
    return success(driver_service.deactivate_driver(driver_id), "Driver deactivated successfully")
