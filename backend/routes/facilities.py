from flask import Blueprint, request

from services import facility_service
from utils.response import error, success
from utils.validators import missing_fields

facilities_bp = Blueprint("facilities", __name__)


@facilities_bp.get("/facilities")
def list_facilities():
    return success(facility_service.list_facilities(), "Facilities loaded")


@facilities_bp.get("/facilities/<facility_id>")
def get_facility(facility_id):
    facility = facility_service.get_facility(facility_id)
    return success(facility, "Facility loaded") if facility else error("Facility not found", "FACILITY_NOT_FOUND", 404)


@facilities_bp.post("/facilities")
def create_facility():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["name", "facility_type", "address"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    return success(facility_service.create_facility(data), "Facility created successfully", 201)


@facilities_bp.put("/facilities/<facility_id>")
def update_facility(facility_id):
    if not facility_service.get_facility(facility_id):
        return error("Facility not found", "FACILITY_NOT_FOUND", 404)
    return success(facility_service.update_facility(facility_id, request.get_json(silent=True) or {}), "Facility updated successfully")


@facilities_bp.delete("/facilities/<facility_id>")
def delete_facility(facility_id):
    if not facility_service.get_facility(facility_id):
        return error("Facility not found", "FACILITY_NOT_FOUND", 404)
    return success(facility_service.deactivate_facility(facility_id), "Facility deactivated successfully")
