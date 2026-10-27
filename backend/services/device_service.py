from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from config import Config
from services.common import collection, create_document, get_document, list_documents, now, soft_delete, update_document
from utils.id_generator import generate_id

COLLECTION = "devices"
FIELD = "device_id"
ACTIVE_TRANSPORT_STATUSES = {"Created", "Loaded", "In Transit", "Arrived", "Mismatch", "Verified"}
ASSIGNABLE_VEHICLE_STATUSES = {"Available", "Assigned", "In Transit"}


def list_devices():
    devices = list_documents(COLLECTION, sort_field="created_at")
    for device in devices:
        try:
            _, _, transport = resolve_device_transport(device["device_id"])
            device["active_transport_id"] = transport["transport_id"]
            device["transport_assignment_error"] = None
        except (LookupError, ValueError) as exc:
            device["active_transport_id"] = None
            device["transport_assignment_error"] = str(exc)
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
    requested_device_id = data.pop("device_id", None) or generate_id("ESP")
    vehicle_id = data.get("vehicle_id")
    vehicle = collection("vehicles").find_one({"vehicle_id": vehicle_id})
    if not vehicle:
        raise LookupError("Vehicle not found")
    if vehicle.get("status") not in ASSIGNABLE_VEHICLE_STATUSES:
        raise ValueError("Vehicle is not eligible for device assignment")
    if collection(COLLECTION).find_one({"device_id": requested_device_id}):
        raise RuntimeError("Device ID is already registered")
    if collection(COLLECTION).find_one({"vehicle_id": vehicle_id}):
        raise RuntimeError("Vehicle already has a device assigned")

    assignments = collection("device_assignments")
    device_claim = {"_id": f"device:{requested_device_id}", "device_id": requested_device_id, "vehicle_id": vehicle_id}
    vehicle_claim = {"_id": f"vehicle:{vehicle_id}", "device_id": requested_device_id, "vehicle_id": vehicle_id}
    try:
        assignments.insert_one(device_claim)
        try:
            assignments.insert_one(vehicle_claim)
        except DuplicateKeyError:
            assignments.delete_one({"_id": device_claim["_id"]})
            raise
    except DuplicateKeyError as exc:
        raise RuntimeError("Device or vehicle already has an assigned device") from exc

    claimed = collection("vehicles").update_one(
        {
            "vehicle_id": vehicle_id,
            "$or": [{"device_id": {"$exists": False}}, {"device_id": None}],
        },
        {"$set": {"device_id": requested_device_id, "updated_at": now()}},
    )
    if not claimed.matched_count:
        assignments.delete_one({"_id": device_claim["_id"]})
        assignments.delete_one({"_id": vehicle_claim["_id"]})
        raise RuntimeError("Vehicle already has a device assigned")

    data.setdefault("status", "active")
    data.setdefault("device_type", "ESP32")
    data.setdefault("last_seen", None)
    try:
        return create_document(COLLECTION, FIELD, "ESP", data, identifier=requested_device_id)
    except Exception:
        collection("vehicles").update_one(
            {"vehicle_id": vehicle_id, "device_id": requested_device_id},
            {"$unset": {"device_id": ""}},
        )
        assignments.delete_one({"_id": device_claim["_id"]})
        assignments.delete_one({"_id": vehicle_claim["_id"]})
        raise


def update_device(device_id, data):
    updates = dict(data)
    has_vehicle_assignment = "vehicle_id" in updates
    new_vehicle_id = updates.pop("vehicle_id", None)
    updates.pop("device_id", None)
    current = get_device(device_id)
    if not current:
        return None
    if has_vehicle_assignment:
        if not isinstance(new_vehicle_id, str) or not new_vehicle_id.strip():
            raise ValueError("A non-empty vehicle_id is required")
        if new_vehicle_id != current.get("vehicle_id"):
            return _reassign_device(device_id, current, new_vehicle_id, updates)
    return update_document(COLLECTION, FIELD, device_id, updates)


def deactivate_device(device_id):
    return update_device(device_id, {"status": "inactive"})


def _reassign_device(device_id, current, new_vehicle_id, updates):
    old_vehicle_id = current.get("vehicle_id")
    old_vehicle = collection("vehicles").find_one({"vehicle_id": old_vehicle_id})
    if not old_vehicle:
        raise LookupError("Current vehicle not found")
    new_vehicle = collection("vehicles").find_one({"vehicle_id": new_vehicle_id})
    if not new_vehicle:
        raise LookupError("Vehicle not found")
    if new_vehicle.get("status") not in ASSIGNABLE_VEHICLE_STATUSES:
        raise ValueError("Vehicle is not eligible for device assignment")

    other_device = collection(COLLECTION).find_one({
        "vehicle_id": new_vehicle_id,
        FIELD: {"$ne": device_id},
    })
    if other_device or new_vehicle.get("device_id") not in (None, device_id):
        raise RuntimeError("Vehicle already has a device assigned")

    assignments = collection("device_assignments")
    device_claim_id = f"device:{device_id}"
    old_vehicle_claim_id = f"vehicle:{old_vehicle_id}"
    new_vehicle_claim_id = f"vehicle:{new_vehicle_id}"
    device_claim = assignments.find_one({"_id": device_claim_id})
    old_vehicle_claim = assignments.find_one({"_id": old_vehicle_claim_id})
    new_vehicle_claim = assignments.find_one({"_id": new_vehicle_claim_id})
    if device_claim and device_claim.get("vehicle_id") != old_vehicle_id:
        raise ValueError("Device assignment registry is inconsistent")
    if old_vehicle_claim and old_vehicle_claim.get("device_id") != device_id:
        raise ValueError("Vehicle assignment registry is inconsistent")
    if new_vehicle_claim and new_vehicle_claim.get("device_id") != device_id:
        raise RuntimeError("Vehicle already has a device assigned")
    if old_vehicle.get("device_id") not in (None, device_id):
        raise ValueError("Current vehicle assignment is inconsistent")

    new_claim_inserted = False
    if not new_vehicle_claim:
        try:
            assignments.insert_one({
                "_id": new_vehicle_claim_id,
                "device_id": device_id,
                "vehicle_id": new_vehicle_id,
            })
            new_claim_inserted = True
        except DuplicateKeyError as exc:
            raise RuntimeError("Vehicle already has a device assigned") from exc

    reserved = collection("vehicles").update_one(
        {
            "vehicle_id": new_vehicle_id,
            "$or": [{"device_id": {"$exists": False}}, {"device_id": None}],
        },
        {"$set": {"device_id": device_id, "updated_at": now()}},
    )
    if not reserved.matched_count:
        if new_claim_inserted:
            assignments.delete_one({"_id": new_vehicle_claim_id})
        raise RuntimeError("Vehicle already has a device assigned")

    device_updated = False
    device_claim_updated = False
    device_claim_inserted = False
    old_vehicle_released = False
    try:
        changed = collection(COLLECTION).update_one(
            {FIELD: device_id, "vehicle_id": old_vehicle_id},
            {"$set": {"vehicle_id": new_vehicle_id, **updates, "updated_at": now()}},
        )
        if not changed.matched_count:
            raise RuntimeError("Device assignment changed during reassignment")
        device_updated = True

        if device_claim:
            claim_update = assignments.update_one(
                {"_id": device_claim_id, "vehicle_id": old_vehicle_id},
                {"$set": {"device_id": device_id, "vehicle_id": new_vehicle_id}},
            )
            if not claim_update.matched_count:
                raise RuntimeError("Device assignment registry changed during reassignment")
            device_claim_updated = True
        else:
            assignments.insert_one({
                "_id": device_claim_id,
                "device_id": device_id,
                "vehicle_id": new_vehicle_id,
            })
            device_claim_inserted = True

        reassigned_device = get_device(device_id)

        if old_vehicle.get("device_id") == device_id:
            released = collection("vehicles").update_one(
                {"vehicle_id": old_vehicle_id, "device_id": device_id},
                {"$unset": {"device_id": ""}, "$set": {"updated_at": now()}},
            )
            if not released.matched_count:
                raise RuntimeError("Current vehicle assignment changed during reassignment")
            old_vehicle_released = True
        assignments.delete_one({"_id": old_vehicle_claim_id})
        return reassigned_device
    except Exception:
        if device_updated:
            restore = {"vehicle_id": old_vehicle_id, "updated_at": now()}
            unset = {}
            for field in updates:
                if field in current:
                    restore[field] = current[field]
                else:
                    unset[field] = ""
            rollback = {"$set": restore}
            if unset:
                rollback["$unset"] = unset
            collection(COLLECTION).update_one(
                {FIELD: device_id, "vehicle_id": new_vehicle_id},
                rollback,
            )
        if device_claim_updated:
            assignments.update_one(
                {"_id": device_claim_id, "vehicle_id": new_vehicle_id},
                {"$set": {"device_id": device_id, "vehicle_id": old_vehicle_id}},
            )
        elif device_claim_inserted:
            assignments.delete_one({"_id": device_claim_id})
        collection("vehicles").update_one(
            {"vehicle_id": new_vehicle_id, "device_id": device_id},
            {"$unset": {"device_id": ""}, "$set": {"updated_at": now()}},
        )
        if new_claim_inserted:
            assignments.delete_one({"_id": new_vehicle_claim_id})
        if old_vehicle_released:
            collection("vehicles").update_one(
                {"vehicle_id": old_vehicle_id},
                {"$set": {"device_id": device_id, "updated_at": now()}},
            )
        raise


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
    if vehicle.get("status") not in ASSIGNABLE_VEHICLE_STATUSES:
        raise ValueError("Vehicle is not eligible for device telemetry")

    if vehicle.get("device_id") not in (None, device_id):
        raise ValueError("Device and vehicle assignments are inconsistent")
    other_device = collection(COLLECTION).find_one({
        "vehicle_id": vehicle_id,
        FIELD: {"$ne": device_id},
    })
    if other_device:
        raise ValueError("Multiple devices are assigned to this vehicle")
    assignments = collection("device_assignments")
    device_claim = assignments.find_one({"_id": f"device:{device_id}"})
    vehicle_claim = assignments.find_one({"_id": f"vehicle:{vehicle_id}"})
    if bool(device_claim) != bool(vehicle_claim):
        raise ValueError("Device assignment registry is incomplete")
    if device_claim and (
        device_claim.get("vehicle_id") != vehicle_id
        or vehicle_claim.get("device_id") != device_id
    ):
        raise ValueError("Device assignment registry is inconsistent")

    active_transports = list(collection("transport_records").find(
        {"vehicle_id": vehicle_id, "status": {"$in": list(ACTIVE_TRANSPORT_STATUSES)}},
    ))

    if not active_transports:
        assigned_transport_id = vehicle.get("active_transport_id")
        if assigned_transport_id:
            assigned_transport = collection("transport_records").find_one(
                {"transport_id": assigned_transport_id}
            )
            if (
                assigned_transport
                and assigned_transport.get("status") in ACTIVE_TRANSPORT_STATUSES
                and assigned_transport.get("vehicle_id") != vehicle_id
            ):
                raise ValueError("Vehicle and active transport assignments are inconsistent")
        raise LookupError("No active transport")
    if len(active_transports) > 1:
        transport_ids = ", ".join(item.get("transport_id", "UNKNOWN") for item in active_transports[:5])
        raise ValueError(f"Multiple active transports for vehicle {vehicle_id}: {transport_ids}")

    transport = active_transports[0]
    if transport.get("vehicle_id") != vehicle_id:
        raise ValueError("Transport is not assigned to the device's vehicle")
    if vehicle.get("active_transport_id") != transport.get("transport_id"):
        raise ValueError("Vehicle and active transport assignments are inconsistent")
    if vehicle.get("current_site_id") != transport.get("site_id"):
        raise ValueError("Vehicle and transport site assignments are inconsistent")
    if not transport.get("site_id"):
        raise ValueError("Transport has no construction site")
    if not transport.get("facility_id"):
        raise ValueError("Transport has no facility")

    site = collection("construction_sites").find_one({"site_id": transport["site_id"]})
    if not site:
        raise LookupError("Transport construction site not found")
    if site.get("status") != "Active":
        raise ValueError("Transport construction site is not active")
    facility = collection("facilities").find_one({"facility_id": transport["facility_id"]})
    if not facility:
        raise LookupError("Transport facility not found")
    if facility.get("status") != "Active" or not facility.get("authorized"):
        raise ValueError("Transport facility is not active and authorized")

    return device, vehicle, transport


def touch_device(device_id, timestamp=None):
    value = timestamp or now()
    collection(COLLECTION).update_one({FIELD: device_id}, {"$set": {"last_seen": value, "updated_at": now()}})