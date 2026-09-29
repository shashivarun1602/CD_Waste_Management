from datetime import datetime, timezone

from config import Config
from services.common import collection, create_document, get_document, list_documents, now, soft_delete, update_document

COLLECTION = "devices"
FIELD = "device_id"
ACTIVE_TRANSPORT_STATUSES = {"Created", "Loaded", "In Transit", "Arrived", "Mismatch", "Verified"}


def list_devices():
    devices = list_documents(COLLECTION, sort_field="created_at")
    for device in devices:
        transport = collection("transport_records").find_one(
            {"vehicle_id": device.get("vehicle_id"), "status": {"$in": list(ACTIVE_TRANSPORT_STATUSES)}},
            {"_id": 0, "transport_id": 1},
            sort=[("created_at", -1)],
        )
        device["active_transport_id"] = transport.get("transport_id") if transport else None
        device["online_status"] = _online_status(device.get("status"), device.get("last_seen"))
        device["latest_gps"] = collection("gps_tracking").find_one(
            {"device_id": device.get("device_id")},
            {"_id": 0, "latitude": 1, "longitude": 1, "satellites": 1, "gps_fix": 1, "timestamp": 1},
            sort=[("timestamp", -1)],
        )
        device["latest_weight"] = collection("weight_readings").find_one(
            {"device_id": device.get("device_id")},
            {"_id": 0, "raw_value": 1, "calibration_status": 1, "weight_kg": 1, "timestamp": 1},
            sort=[("timestamp", -1)],
        )
    return devices


def _online_status(device_status, last_seen):
    if str(device_status or "").lower() != "active" or not last_seen:
        return "OFFLINE"
    try:
        seen_at = datetime.fromisoformat(str(last_seen).replace("Z", "+00:00"))
        if seen_at.tzinfo is None:
            seen_at = seen_at.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return "OFFLINE"
    age_seconds = (datetime.now(timezone.utc) - seen_at).total_seconds()
    return "ONLINE" if 0 <= age_seconds <= Config.DEVICE_ONLINE_WINDOW_SECONDS else "OFFLINE"


def get_device(device_id):
    return get_document(COLLECTION, FIELD, device_id)


def create_device(data):
    data = dict(data)
    requested_device_id = data.pop("device_id", None)
    data.setdefault("status", "active")
    data.setdefault("device_type", "ESP32")
    data.setdefault("last_seen", None)
    return create_document(COLLECTION, FIELD, "ESP", data, identifier=requested_device_id)


def update_device(device_id, data):
    return update_document(COLLECTION, FIELD, device_id, data)


def deactivate_device(device_id):
    return update_device(device_id, {"status": "inactive"})


def resolve_device_transport(device_id, transport_id=None):
    device = collection(COLLECTION).find_one({FIELD: device_id})
    if not device:
        raise LookupError("Device not found")
    if str(device.get("status", "")).lower() != "active":
        raise ValueError("Device inactive")

    vehicle_id = device.get("vehicle_id")
    if not vehicle_id:
        raise ValueError("Device has no vehicle")

    vehicle = collection("vehicles").find_one({"vehicle_id": vehicle_id})
    if not vehicle:
        raise LookupError("Vehicle not found")

    transport_records = collection("transport_records")
    if transport_id:
        transport = transport_records.find_one({
            "transport_id": transport_id,
            "vehicle_id": vehicle_id,
            "status": {"$in": list(ACTIVE_TRANSPORT_STATUSES)},
        })
        if transport:
            return device, vehicle, transport
        other_transport = transport_records.find_one({"transport_id": transport_id})
        if other_transport and other_transport.get("vehicle_id") != vehicle_id:
            raise ValueError("Transport is not assigned to this device's vehicle")
        raise LookupError("No active transport for device and vehicle")

    active_transports = list(transport_records.find(
        {"vehicle_id": vehicle_id, "status": {"$in": list(ACTIVE_TRANSPORT_STATUSES)}},
        sort=[("created_at", -1)],
    ))

    if not active_transports:
        raise LookupError("No active transport")
    if len(active_transports) > 1:
        transport_ids = ", ".join(item.get("transport_id", "UNKNOWN") for item in active_transports[:5])
        raise ValueError(f"Multiple active transports for vehicle {vehicle_id}: {transport_ids}")

    return device, vehicle, active_transports[0]


def touch_device(device_id, timestamp=None):
    value = timestamp or now()
    collection(COLLECTION).update_one({FIELD: device_id}, {"$set": {"last_seen": value, "updated_at": now()}})