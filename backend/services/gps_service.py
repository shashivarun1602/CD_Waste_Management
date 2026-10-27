from services.common import collection, create_document, list_documents, now
from services.device_service import resolve_device_transport, touch_device
from services.route_service import evaluate_route, set_route_origin


def add_gps_point(data):
    data = dict(data)
    data.setdefault("source", "manual")
    data.setdefault("timestamp", now())
    return create_document("gps_tracking", "tracking_id", "GPS", data)


def list_gps_points(transport_id=None):
    query = {"transport_id": transport_id} if transport_id else {}
    return list_documents("gps_tracking", query, "timestamp")


def latest_gps_point(transport_id):
    document = collection("gps_tracking").find_one({"transport_id": transport_id}, sort=[("timestamp", -1)])
    from utils.response import document_to_dict
    return document_to_dict(document)


def add_device_gps_point(data):
    device_id = data["device_id"]
    device, vehicle, transport = resolve_device_transport(device_id)
    latitude = float(data["latitude"]) if data.get("latitude") is not None else None
    longitude = float(data["longitude"]) if data.get("longitude") is not None else None
    timestamp = data.get("timestamp") or now()
    gps_fix = data.get("gps_fix", True)
    if gps_fix:
        set_route_origin(transport["transport_id"], latitude, longitude)
        refreshed_transport = collection("transport_records").find_one({"transport_id": transport["transport_id"]})
        route_status, deviation = evaluate_route(refreshed_transport, latitude, longitude)
    else:
        route_status, deviation = "NO_FIX", None
    point = create_document("gps_tracking", "tracking_id", "GPS", {
        "device_id": device["device_id"],
        "vehicle_id": vehicle["vehicle_id"],
        "transport_id": transport["transport_id"],
        "latitude": latitude,
        "longitude": longitude,
        "satellites": data.get("satellites"),
        "gps_fix": gps_fix,
        "timestamp": timestamp,
        "route_status": route_status,
        "deviation_distance_meters": deviation,
        "source": "device",
    })
    collection("transport_records").update_one({"transport_id": transport["transport_id"]}, {"$set": {
        "latest_gps": {"latitude": latitude, "longitude": longitude, "satellites": data.get("satellites"), "gps_fix": gps_fix, "timestamp": timestamp},
        "latest_route_status": route_status,
        "updated_at": now(),
    }})
    received_at = now()
    touch_device(device_id, received_at)
    collection("vehicles").update_one({"vehicle_id": vehicle["vehicle_id"]}, {"$set": {"last_seen": received_at, "updated_at": received_at}})
    point.update({"device_id": device["device_id"], "vehicle_id": vehicle["vehicle_id"], "transport_id": transport["transport_id"], "route_status": route_status})
    return point
