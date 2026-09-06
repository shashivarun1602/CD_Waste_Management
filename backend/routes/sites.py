from flask import Blueprint, request

from services import site_service
from utils.response import error, success
from utils.validators import missing_fields

sites_bp = Blueprint("sites", __name__)


@sites_bp.get("/sites")
def list_sites():
    return success(site_service.list_sites(), "Sites loaded")


@sites_bp.get("/sites/<site_id>")
def get_site(site_id):
    site = site_service.get_site(site_id)
    return success(site, "Site loaded") if site else error("Site not found", "SITE_NOT_FOUND", 404)


@sites_bp.post("/sites")
def create_site():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["name", "address"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    return success(site_service.create_site(data), "Site created successfully", 201)


@sites_bp.put("/sites/<site_id>")
def update_site(site_id):
    if not site_service.get_site(site_id):
        return error("Site not found", "SITE_NOT_FOUND", 404)
    return success(site_service.update_site(site_id, request.get_json(silent=True) or {}), "Site updated successfully")


@sites_bp.delete("/sites/<site_id>")
def delete_site(site_id):
    if not site_service.get_site(site_id):
        return error("Site not found", "SITE_NOT_FOUND", 404)
    return success(site_service.deactivate_site(site_id), "Site deactivated successfully")
