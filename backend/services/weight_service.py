from services.common import collection, create_document, now
from services.device_service import resolve_device_transport, touch_device


def add_device_weight(data):
    device, vehicle, transport = resolve_device_transport(data["device_id"])
    weight = float(data["weight_kg"])
    timestamp = data.get("timestamp") or now()
    reading = create_document("weight_readings", "reading_id", "WGT", {
        "device_id": device["device_id"],
        "vehicle_id": vehicle["vehicle_id"],
        "transport_id": transport["transport_id"],
        "weight_kg": weight,
        "timestamp": timestamp,
        "source": "device",
    })
    updates = {"latest_weight_kg": weight, "latest_weight_at": timestamp, "updated_at": now()}
    if transport.get("status") == "Created":
        updates.update({"status": "Loaded", "loaded_weight_kg": weight, "weight_source": "device", "device_id": device["device_id"]})
    elif transport.get("status") == "Arrived":
        updates.update({"received_weight_kg": weight, "received_weight_source": "device", "received_device_id": device["device_id"]})
    collection("transport_records").update_one({"transport_id": transport["transport_id"]}, {"$set": updates})
    touch_device(device["device_id"], timestamp)
    return {"reading": reading, "device_id": device["device_id"], "vehicle_id": vehicle["vehicle_id"], "transport_id": transport["transport_id"], "weight_kg": weight}


def list_weight_readings(transport_id=None):
    query = {"transport_id": transport_id} if transport_id else {}
    cursor = collection("weight_readings").find(query).sort("timestamp", -1)
    from utils.response import document_to_dict
    return [document_to_dict(item) for item in cursor]