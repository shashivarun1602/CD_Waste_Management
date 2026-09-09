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
    return devices


def get_device(device_id):
    return get_document(COLLECTION, FIELD, device_id)


def create_device(data):
    data = dict(data)
    data.setdefault("status", "active")
    data.setdefault("device_type", "ESP32")
    data.setdefault("last_seen", None)
    return create_document(COLLECTION, FIELD, "ESP", data)


def update_device(device_id, data):
    return update_document(COLLECTION, FIELD, device_id, data)


def deactivate_device(device_id):
    return update_device(device_id, {"status": "inactive"})


def resolve_device_transport(device_id):
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
    transport = collection("transport_records").find_one(
        {"vehicle_id": vehicle_id, "status": {"$in": list(ACTIVE_TRANSPORT_STATUSES)}},
        sort=[("created_at", -1)],
    )
    if not transport:
        raise LookupError("No active transport")
    return device, vehicle, transport


def touch_device(device_id, timestamp=None):
    value = timestamp or now()
    collection(COLLECTION).update_one({FIELD: device_id}, {"$set": {"last_seen": value, "updated_at": now()}})