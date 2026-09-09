from flask import Blueprint, request

from services import facility_service
from utils.response import error, success
from utils.validators import missing_fields

facilities_bp = Blueprint("facilities", __name__)


@facilities_bp.get("/facilities")
def list_facilities():
    return success(facility_service.list_facilities(), "Facilities loaded")


@facilities_bp.get("/facilities/recommend")
def recommend_facilities():
    waste_type = request.args.get("waste_type")
    latitude = request.args.get("latitude")
    longitude = request.args.get("longitude")
    if not waste_type or latitude is None or longitude is None:
        return error("waste_type, latitude, and longitude are required", "MISSING_FIELDS")
    try:
        coordinates = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return error("latitude and longitude must be numbers", "INVALID_LOCATION")
    return success(facility_service.recommend_facility(waste_type, *coordinates), "Facility recommendations loaded")


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
    for field in ("latitude", "longitude"):
        if data.get(field) is not None:
            try:
                data[field] = float(data[field])
            except (TypeError, ValueError):
                return error(f"{field} must be a number", "INVALID_LOCATION")
    if data.get("latitude") is not None and not -90 <= data["latitude"] <= 90:
        return error("latitude must be between -90 and 90", "INVALID_LOCATION")
    if data.get("longitude") is not None and not -180 <= data["longitude"] <= 180:
        return error("longitude must be between -180 and 180", "INVALID_LOCATION")
    if not isinstance(data.get("authorized_waste_types", []), list):
        return error("authorized_waste_types must be a list", "INVALID_WASTE_TYPES")
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
