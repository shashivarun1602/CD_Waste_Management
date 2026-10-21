from pymongo import ReturnDocument

from services.common import collection, create_document, get_document, list_documents, now, soft_delete, update_document
from services.transport_service import ACTIVE_STATUSES

COLLECTION = "vehicles"
FIELD = "vehicle_id"


def list_vehicles():
    return list_documents(COLLECTION, sort_field="created_at")


def get_vehicle(vehicle_id):
    return get_document(COLLECTION, FIELD, vehicle_id)


def create_vehicle(data):
    data.setdefault("status", "Available")
    data.setdefault("current_site_id", None)
    return create_document(COLLECTION, FIELD, "VEH", data)


def update_vehicle(vehicle_id, data):
    protected_fields = {"current_site_id", "active_transport_id", "device_id"}
    if protected_fields.intersection(data):
        raise ValueError("Use the dedicated assignment operation to change vehicle assignments")
    return update_document(COLLECTION, FIELD, vehicle_id, data)


def assign_vehicle_to_site(vehicle_id, site_id):
    site = collection("construction_sites").find_one({"site_id": site_id})
    if not site:
        raise LookupError("Construction site not found")
    if site.get("status") != "Active":
        raise ValueError("Construction site is not active")

    vehicle = collection(COLLECTION).find_one({FIELD: vehicle_id})
    if not vehicle:
        raise LookupError("Vehicle not found")
    if vehicle.get("status") not in {"Available", "Assigned"}:
        raise ValueError("Vehicle is not eligible for site assignment")
    if vehicle.get("active_transport_id") or collection("transport_records").find_one(
        {"vehicle_id": vehicle_id, "status": {"$in": list(ACTIVE_STATUSES)}}
    ):
        raise RuntimeError("Vehicle cannot be reassigned while it has an active transport")

    assigned = collection(COLLECTION).find_one_and_update(
        {
            FIELD: vehicle_id,
            "status": {"$in": ["Available", "Assigned"]},
            "active_transport_id": {"$in": [None]},
        },
        {"$set": {"current_site_id": site_id, "status": "Assigned", "updated_at": now()}},
        return_document=ReturnDocument.AFTER,
    )
    if not assigned:
        raise RuntimeError("Vehicle changed or became busy during site assignment")
    return assigned


def deactivate_vehicle(vehicle_id):
    return soft_delete(COLLECTION, FIELD, vehicle_id)
