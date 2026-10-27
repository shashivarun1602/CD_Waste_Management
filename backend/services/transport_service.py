from pymongo import ReturnDocument

from services.common import collection, create_document, get_document, list_documents, now, update_document
from services.gps_service import latest_gps_point
from services.verification_service import verify_weights
from utils.id_generator import generate_id

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
    transports = list_documents(COLLECTION, query, "created_at")
    for transport in transports:
        waste = collection("waste_records").find_one({"waste_id": transport.get("waste_id")}, {"_id": 0, "waste_type": 1})
        device = collection("devices").find_one({"vehicle_id": transport.get("vehicle_id")}, {"_id": 0, "device_id": 1})
        latest_weight = collection("weight_readings").find_one({"transport_id": transport.get("transport_id")}, sort=[("timestamp", -1)])
        transport["waste_type"] = waste.get("waste_type") if waste else None
        transport["device_id"] = (device.get("device_id") if device else None) or transport.get("device_id")
        transport["latest_weight_kg"] = latest_weight.get("weight_kg") if latest_weight else transport.get("latest_weight_kg")
        transport["latest_route_status"] = transport.get("latest_route_status", "NO_ROUTE")
    return transports


def get_transport(transport_id):
    transport = get_document(COLLECTION, FIELD, transport_id)
    if transport:
        transport["latest_gps"] = latest_gps_point(transport_id)
        transport["gps_history"] = list_documents("gps_tracking", {"transport_id": transport_id}, "timestamp")
        transport["latest_sensor_reading"] = collection("weight_readings").find_one(
            {"transport_id": transport_id},
            {"_id": 0, "raw_value": 1, "calibration_status": 1, "weight_kg": 1, "timestamp": 1},
            sort=[("timestamp", -1)],
        )
        device = collection("devices").find_one({"vehicle_id": transport.get("vehicle_id")}, {"_id": 0, "device_id": 1})
        transport["device_id"] = (device.get("device_id") if device else None) or transport.get("device_id")
    return transport


def _reference_exists(collection_name, field, identifier):
    return collection(collection_name).find_one({field: identifier})


def create_transport(data):
    references = (
        ("construction_sites", "site_id", data.get("site_id"), "site"),
        ("vehicles", "vehicle_id", data.get("vehicle_id"), "vehicle"),
        ("facilities", "facility_id", data.get("facility_id"), "facility"),
    )
    if data.get("driver_id"):
        references += (("drivers", "driver_id", data["driver_id"], "driver"),)
    for collection_name, field, identifier, label in references:
        if not identifier or not _reference_exists(collection_name, field, identifier):
            raise ValueError(f"{label.title()} not found")
    site = _reference_exists("construction_sites", "site_id", data["site_id"])
    if site.get("status") != "Active":
        raise ValueError("Construction site is not active")
    facility = _reference_exists("facilities", "facility_id", data["facility_id"])
    if facility.get("status") != "Active" or not facility.get("authorized"):
        raise ValueError("Facility is not active and authorized")
    active_query = {"status": {"$in": list(ACTIVE_STATUSES)}, "vehicle_id": data["vehicle_id"]}
    if data.get("driver_id"):
        active_query = {"status": {"$in": list(ACTIVE_STATUSES)}, "$or": [{"vehicle_id": data["vehicle_id"]}, {"driver_id": data["driver_id"]}]}
    if collection(COLLECTION).find_one(active_query):
        raise RuntimeError("Vehicle or driver is already assigned to an active transport")

    vehicle_id = data["vehicle_id"]
    vehicle = _reference_exists("vehicles", "vehicle_id", vehicle_id)
    if vehicle.get("status") not in {"Available", "Assigned"}:
        raise ValueError("Vehicle is not eligible for a transport")
    current_site_id = vehicle.get("current_site_id")
    if current_site_id and current_site_id != data["site_id"]:
        raise ValueError("Vehicle is assigned to another site; reassign it before creating this transport")
    if vehicle.get("active_transport_id"):
        raise RuntimeError("Vehicle is already assigned to an active transport")

    data = dict(data)
    data.update({"status": "Created", "source": data.get("source", "manual"), "loaded_weight_kg": None, "received_weight_kg": None, "weight_difference_kg": None, "difference_percentage": None, "weight_status": "Pending", "started_at": None, "arrived_at": None, "verified_at": None, "completed_at": None})
    transport_id = generate_id("TRN")
    timestamp = now()
    reservation = collection("vehicles").find_one_and_update(
        {
            "vehicle_id": vehicle_id,
            "status": {"$in": ["Available", "Assigned"]},
            "active_transport_id": {"$in": [None]},
            "$or": [{"current_site_id": None}, {"current_site_id": data["site_id"]}],
        },
        {"$set": {"status": "Assigned", "current_site_id": data["site_id"], "active_transport_id": transport_id, "updated_at": timestamp}},
        return_document=ReturnDocument.BEFORE,
    )
    if not reservation:
        raise RuntimeError("Vehicle or driver is already assigned to an active transport")

    try:
        transport = create_document(COLLECTION, FIELD, "TRN", data, identifier=transport_id)
    except Exception:
        restore = {"status": reservation.get("status", "Available"), "updated_at": now()}
        unset = {"active_transport_id": ""}
        if "current_site_id" in reservation:
            restore["current_site_id"] = reservation["current_site_id"]
        else:
            unset["current_site_id"] = ""
        collection("vehicles").update_one(
            {"vehicle_id": vehicle_id, "active_transport_id": transport_id},
            {"$set": restore, "$unset": unset},
        )
        raise

    if data.get("driver_id"):
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
        if transport.get("driver_id"):
            collection("drivers").update_one({"driver_id": transport["driver_id"]}, {"$set": {"status": "On Trip", "updated_at": now()}})
    elif next_status == "Arrived":
        updates["arrived_at"] = now()
    elif next_status in {"Verified", "Mismatch"}:
        updates["verified_at"] = now()
    elif next_status == "Completed":
        updates["completed_at"] = now()
        collection("vehicles").update_one(
            {
                "vehicle_id": transport["vehicle_id"],
                "$or": [
                    {"active_transport_id": transport_id},
                    {"active_transport_id": None, "current_site_id": transport.get("site_id")},
                ],
            },
            {"$set": {"status": "Available", "current_site_id": None, "updated_at": now()}, "$unset": {"active_transport_id": ""}},
        )
        if transport.get("driver_id"):
            collection("drivers").update_one({"driver_id": transport["driver_id"]}, {"$set": {"status": "Available", "updated_at": now()}})
    return update_document(COLLECTION, FIELD, transport_id, updates)


def load_transport(transport_id, weight_kg, source="manual", device_id=None):
    return _change_status(transport_id, "Loaded", {"loaded_weight_kg": weight_kg, "weight_source": source, "device_id": device_id})


def start_transport(transport_id):
    return _change_status(transport_id, "In Transit")


def arrive_transport(transport_id, received_weight_kg=None, source="manual", device_id=None):
    updates = {"received_weight_kg": received_weight_kg, "received_weight_source": source, "received_device_id": device_id} if received_weight_kg is not None else {}
    return _change_status(transport_id, "Arrived", updates)


def _latest_calibrated_reading(transport_id):
    reading = collection("weight_readings").find_one(
        {"transport_id": transport_id, "weight_kg": {"$gt": 0}, "calibration_status": "SET"},
        {"_id": 0, "device_id": 1, "weight_kg": 1},
        sort=[("timestamp", -1)],
    )
    if not reading:
        raise ValueError("No calibrated sensor weight is available to capture")
    return reading


def capture_loaded_weight(transport_id):
    transport = collection(COLLECTION).find_one({FIELD: transport_id})
    if not transport:
        raise LookupError("Transport not found")
    if transport.get("loaded_weight_kg") is not None:
        raise ValueError("Official loaded weight has already been captured")
    reading = _latest_calibrated_reading(transport_id)
    return load_transport(transport_id, reading["weight_kg"], "device", reading.get("device_id"))


def capture_received_weight(transport_id):
    transport = collection(COLLECTION).find_one({FIELD: transport_id})
    if not transport:
        raise LookupError("Transport not found")
    if transport.get("status") not in {"In Transit", "Arrived"}:
        raise ValueError("Received weight can only be captured for an in-transit or arrived transport")
    if transport.get("received_weight_kg") is not None:
        raise ValueError("Official received weight has already been captured")
    reading = _latest_calibrated_reading(transport_id)
    if transport.get("status") == "In Transit":
        return arrive_transport(transport_id, reading["weight_kg"], "device", reading.get("device_id"))
    return update_document(COLLECTION, FIELD, transport_id, {
        "received_weight_kg": reading["weight_kg"],
        "received_weight_source": "device",
        "received_device_id": reading.get("device_id"),
    })


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


def close_mismatch_transport(transport_id, reason):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("A mismatch review reason is required")
    reason = reason.strip()
    if len(reason) > 500:
        raise ValueError("Mismatch review reason must be 500 characters or fewer")

    transport = collection(COLLECTION).find_one({FIELD: transport_id})
    if not transport:
        raise LookupError("Transport not found")
    if transport.get("status") != "Mismatch" or transport.get("weight_status") != "Mismatch":
        raise ValueError("Only transports with a verified mismatch can be closed")
    loaded_weight = transport.get("loaded_weight_kg")
    received_weight = transport.get("received_weight_kg")
    if loaded_weight is None or received_weight is None:
        raise ValueError("Loaded and received weights are required to close a mismatch")
    if verify_weights(loaded_weight, received_weight)["weight_status"] != "Mismatch":
        raise ValueError("Recorded weights do not satisfy the mismatch verification requirements")

    vehicle = collection("vehicles").find_one({"vehicle_id": transport.get("vehicle_id")})
    if not vehicle or vehicle.get("active_transport_id") != transport_id:
        raise ValueError("Vehicle is no longer assigned to this transport")

    closed_at = now()
    closed = collection(COLLECTION).update_one(
        {
            FIELD: transport_id,
            "status": "Mismatch",
            "weight_status": "Mismatch",
            "loaded_weight_kg": loaded_weight,
            "received_weight_kg": received_weight,
            "$or": [{"mismatch_closed_at": {"$exists": False}}, {"mismatch_closed_at": None}],
        },
        {
            "$set": {
                "status": "Closed",
                "mismatch_closed_from_status": "Mismatch",
                "mismatch_closure_reason": reason,
                "mismatch_reviewed_at": closed_at,
                "mismatch_closed_at": closed_at,
                "updated_at": closed_at,
            }
        },
    )
    if not closed.matched_count:
        raise ValueError("Mismatch transport was changed or already closed")

    released = collection("vehicles").update_one(
        {"vehicle_id": transport["vehicle_id"], "active_transport_id": transport_id},
        {
            "$set": {"status": "Available", "current_site_id": None, "updated_at": now()},
            "$unset": {"active_transport_id": ""},
        },
    )
    if not released.matched_count:
        collection(COLLECTION).update_one(
            {
                FIELD: transport_id,
                "status": "Closed",
                "mismatch_closed_at": closed_at,
            },
            {
                "$set": {"status": "Mismatch", "updated_at": now()},
                "$unset": {
                    "mismatch_closed_from_status": "",
                    "mismatch_closure_reason": "",
                    "mismatch_reviewed_at": "",
                    "mismatch_closed_at": "",
                },
            },
        )
        raise RuntimeError("Vehicle assignment changed; mismatch closure was not completed")

    if transport.get("driver_id"):
        collection("drivers").update_one(
            {"driver_id": transport["driver_id"]},
            {"$set": {"status": "Available", "updated_at": now()}},
        )
    return get_document(COLLECTION, FIELD, transport_id)


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
