from flask import Blueprint

from db import get_database
from utils.response import success

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/dashboard")
def dashboard():
    database = get_database()
    transport_records = database.transport_records
    stats = {
        "total_sites": database.construction_sites.count_documents({}),
        "active_sites": database.construction_sites.count_documents({"status": "Active"}),
        "total_vehicles": database.vehicles.count_documents({}),
        "available_vehicles": database.vehicles.count_documents({"status": "Available"}),
        "vehicles_in_transit": database.vehicles.count_documents({"status": "In Transit"}),
        "active_transports": transport_records.count_documents({"status": {"$in": ["Created", "Loaded", "In Transit", "Arrived", "Mismatch", "Verified"]}}),
        "completed_transports": transport_records.count_documents({"status": "Completed"}),
        "pending_verification": transport_records.count_documents({"weight_status": "Pending"}),
        "weight_mismatches": transport_records.count_documents({"weight_status": "Mismatch"}),
        "total_waste_transported_kg": sum((item.get("loaded_weight_kg") or 0) for item in transport_records.find({}, {"loaded_weight_kg": 1})),
        "total_waste_received_kg": sum((item.get("received_weight_kg") or 0) for item in transport_records.find({}, {"received_weight_kg": 1})),
        "recent_transports": list(transport_records.find({}, {"_id": 0}).sort("created_at", -1).limit(8)),
    }
    return success(stats, "Dashboard data loaded")
