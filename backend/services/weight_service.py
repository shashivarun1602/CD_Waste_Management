from services.common import collection, create_document, now
from services.device_service import resolve_device_transport, touch_device


def add_device_weight(data):
    device, vehicle, transport = resolve_device_transport(data["device_id"])
    weight = float(data["weight_kg"]) if data.get("weight_kg") is not None else None
    timestamp = data.get("timestamp") or now()
    reading = create_document("weight_readings", "reading_id", "WGT", {
        "device_id": device["device_id"],
        "vehicle_id": vehicle["vehicle_id"],
        "transport_id": transport["transport_id"],
        "raw_value": data.get("raw_value"),
        "calibration_status": data.get("calibration_status", "SET" if weight is not None else "NOT_SET"),
        "weight_kg": weight,
        "timestamp": timestamp,
        "source": "device",
    })
    updates = {"latest_raw_value": data.get("raw_value"), "latest_reading_at": timestamp, "updated_at": now()}
    if weight is not None:
        updates.update({"latest_weight_kg": weight, "latest_weight_at": timestamp})
    collection("transport_records").update_one({"transport_id": transport["transport_id"]}, {"$set": updates})
    received_at = now()
    touch_device(device["device_id"], received_at)
    return {
        "reading": reading,
        "device_id": device["device_id"],
        "vehicle_id": vehicle["vehicle_id"],
        "transport_id": transport["transport_id"],
        "raw_value": data.get("raw_value"),
        "calibration_status": data.get("calibration_status", "SET" if weight is not None else "NOT_SET"),
        "weight_kg": weight,
    }


def list_weight_readings(transport_id=None):
    query = {"transport_id": transport_id} if transport_id else {}
    cursor = collection("weight_readings").find(query).sort("timestamp", -1)
    from utils.response import document_to_dict
    return [document_to_dict(item) for item in cursor]