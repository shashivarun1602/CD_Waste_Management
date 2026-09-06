from services.common import collection, create_document, get_document, list_documents, now, update_document
from services.gps_service import latest_gps_point
from services.verification_service import verify_weights

COLLECTION = "transport_records"
FIELD = "transport_id"
ACTIVE_STATUSES = {"Created", "Loaded", "In Transit", "Arrived", "Mismatch", "Verified"}
TRANSITIONS = {
    "Created": {"Loaded"},
    "Loaded": {"In Transit"},
    "In Transit": {"Arrived"},
    "Arrived": {"Verified", "Mismatch"},
    "Mismatch": set(),
    "Verified": {"Completed"},
    "Completed": set(),
}


def list_transports(query=None):
    return list_documents(COLLECTION, query, "created_at")


def get_transport(transport_id):
    transport = get_document(COLLECTION, FIELD, transport_id)
    if transport:
        transport["latest_gps"] = latest_gps_point(transport_id)
    return transport


def _reference_exists(collection_name, field, identifier):
    return collection(collection_name).find_one({field: identifier})


def create_transport(data):
    references = (
        ("construction_sites", "site_id", data.get("site_id"), "site"),
        ("vehicles", "vehicle_id", data.get("vehicle_id"), "vehicle"),
        ("drivers", "driver_id", data.get("driver_id"), "driver"),
        ("facilities", "facility_id", data.get("facility_id"), "facility"),
        ("waste_records", "waste_id", data.get("waste_id"), "waste record"),
    )
    for collection_name, field, identifier, label in references:
        if not identifier or not _reference_exists(collection_name, field, identifier):
            raise ValueError(f"{label.title()} not found")
    facility = _reference_exists("facilities", "facility_id", data["facility_id"])
    if facility.get("status") != "Active" or not facility.get("authorized"):
        raise ValueError("Facility is not active and authorized")
    active_query = {"status": {"$in": list(ACTIVE_STATUSES)}, "$or": [{"vehicle_id": data["vehicle_id"]}, {"driver_id": data["driver_id"]}]}
    if collection(COLLECTION).find_one(active_query):
        raise RuntimeError("Vehicle or driver is already assigned to an active transport")
    data = dict(data)
    data.update({"status": "Created", "source": data.get("source", "manual"), "loaded_weight_kg": None, "received_weight_kg": None, "weight_difference_kg": None, "difference_percentage": None, "weight_status": "Pending", "started_at": None, "arrived_at": None, "verified_at": None, "completed_at": None})
    transport = create_document(COLLECTION, FIELD, "TRN", data)
    timestamp = now()
    collection("vehicles").update_one({"vehicle_id": data["vehicle_id"]}, {"$set": {"status": "Assigned", "current_site_id": data["site_id"], "updated_at": timestamp}})
    collection("drivers").update_one({"driver_id": data["driver_id"]}, {"$set": {"status": "Assigned", "updated_at": timestamp}})
    return transport


def _change_status(transport_id, next_status, updates=None):
    transport = collection(COLLECTION).find_one({FIELD: transport_id})
    if not transport:
        raise LookupError("Transport not found")
    if next_status not in TRANSITIONS.get(transport.get("status"), set()):
        raise ValueError(f"Invalid lifecycle transition: {transport.get('status')} to {next_status}")
    updates = dict(updates or {})
    updates["status"] = next_status
    if next_status == "In Transit":
        updates["started_at"] = now()
        collection("vehicles").update_one({"vehicle_id": transport["vehicle_id"]}, {"$set": {"status": "In Transit", "updated_at": now()}})
        collection("drivers").update_one({"driver_id": transport["driver_id"]}, {"$set": {"status": "On Trip", "updated_at": now()}})
    elif next_status == "Arrived":
        updates["arrived_at"] = now()
    elif next_status in {"Verified", "Mismatch"}:
        updates["verified_at"] = now()
    elif next_status == "Completed":
        updates["completed_at"] = now()
        collection("vehicles").update_one({"vehicle_id": transport["vehicle_id"]}, {"$set": {"status": "Available", "current_site_id": None, "updated_at": now()}})
        collection("drivers").update_one({"driver_id": transport["driver_id"]}, {"$set": {"status": "Available", "updated_at": now()}})
    return update_document(COLLECTION, FIELD, transport_id, updates)


def load_transport(transport_id, weight_kg, source="manual", device_id=None):
    return _change_status(transport_id, "Loaded", {"loaded_weight_kg": weight_kg, "weight_source": source, "device_id": device_id})


def start_transport(transport_id):
    return _change_status(transport_id, "In Transit")


def arrive_transport(transport_id, received_weight_kg=None, source="manual", device_id=None):
    updates = {"received_weight_kg": received_weight_kg, "received_weight_source": source, "received_device_id": device_id} if received_weight_kg is not None else {}
    return _change_status(transport_id, "Arrived", updates)


def verify_transport(transport_id):
    transport = collection(COLLECTION).find_one({FIELD: transport_id})
    if not transport:
        raise LookupError("Transport not found")
    if transport.get("status") != "Arrived":
        raise ValueError("Only arrived transports can be verified")
    if transport.get("loaded_weight_kg") is None or transport.get("received_weight_kg") is None:
        raise ValueError("Loaded and received weights are required")
    result = verify_weights(transport["loaded_weight_kg"], transport["received_weight_kg"])
    return _change_status(transport_id, result["weight_status"], result)


def complete_transport(transport_id):
    transport = collection(COLLECTION).find_one({FIELD: transport_id})
    if not transport:
        raise LookupError("Transport not found")
    if transport.get("weight_status") != "Verified":
        raise ValueError("Only verified transports can be completed")
    return _change_status(transport_id, "Completed")


def record_weight(transport_id, data):
    transport = collection(COLLECTION).find_one({FIELD: transport_id})
    if not transport:
        raise LookupError("Transport not found")
    if transport.get("status") == "Created":
        return load_transport(transport_id, data["weight_kg"], data.get("source", "manual"), data.get("device_id"))
    if transport.get("status") == "Arrived":
        return update_document(COLLECTION, FIELD, transport_id, {"received_weight_kg": data["weight_kg"], "received_weight_source": data.get("source", "manual"), "received_device_id": data.get("device_id")})
    raise ValueError("Weight can only be recorded for a created or arrived transport")


def vehicle_history(vehicle_id):
    return list_transports({"vehicle_id": vehicle_id})
