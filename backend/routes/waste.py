from flask import Blueprint, request

from services import waste_service
from utils.response import error, success
from utils.validators import missing_fields, positive_number

waste_bp = Blueprint("waste", __name__)


@waste_bp.get("/waste")
def list_waste_records():
    return success(waste_service.list_waste(), "Waste records loaded")


@waste_bp.get("/waste/<waste_id>")
def get_waste(waste_id):
    waste = waste_service.get_waste(waste_id)
    return success(waste, "Waste record loaded") if waste else error("Waste record not found", "WASTE_NOT_FOUND", 404)


@waste_bp.post("/waste")
def create_waste():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["site_id", "waste_type"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    if data.get("estimated_weight_kg") is not None:
        value, message = positive_number(data["estimated_weight_kg"], "estimated_weight_kg")
        if message:
            return error(message, "INVALID_WEIGHT")
        data["estimated_weight_kg"] = value
    return success(waste_service.create_waste(data), "Waste record created successfully", 201)


@waste_bp.put("/waste/<waste_id>")
def update_waste(waste_id):
    if not waste_service.get_waste(waste_id):
        return error("Waste record not found", "WASTE_NOT_FOUND", 404)
    return success(waste_service.update_waste(waste_id, request.get_json(silent=True) or {}), "Waste record updated successfully")


@waste_bp.delete("/waste/<waste_id>")
def delete_waste(waste_id):
    if not waste_service.get_waste(waste_id):
        return error("Waste record not found", "WASTE_NOT_FOUND", 404)
    return success(waste_service.delete_waste(waste_id), "Waste record deactivated successfully")
