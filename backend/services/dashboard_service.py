from collections import defaultdict

from utils.response import document_to_dict

ACTIVE_STATUSES = {"Created", "Loaded", "In Transit", "Arrived", "Mismatch", "Verified"}


def _weight_total(transports, field):
    values = []
    for transport in transports:
        value = transport.get(field)
        if value is None or isinstance(value, bool):
            continue
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return (round(sum(values), 3) if values else None, len(values))


def _summarize_transports(transports):
    loaded_total, loaded_count = _weight_total(transports, "loaded_weight_kg")
    received_total, received_count = _weight_total(transports, "received_weight_kg")
    statuses = [transport.get("status") for transport in transports]
    weight_statuses = [transport.get("weight_status") for transport in transports]
    return {
        "total_transports": len(transports),
        "total_loaded_weight_kg": loaded_total,
        "loaded_weight_records": loaded_count,
        "total_received_weight_kg": received_total,
        "received_weight_records": received_count,
        "completed_transports": sum(status == "Completed" for status in statuses),
        "active_transports": sum(status in ACTIVE_STATUSES for status in statuses),
        "in_transit_transports": sum(status == "In Transit" for status in statuses),
        "verified_transports": sum(status == "Verified" for status in weight_statuses),
        "pending_verification": sum(status == "Pending" for status in weight_statuses),
        "mismatches": sum(status == "Mismatch" for status in statuses)
        + sum(status == "Mismatch" and statuses[index] != "Mismatch" for index, status in enumerate(weight_statuses)),
    }


def _site_summary(site, transports):
    summary = _summarize_transports(transports)
    vehicle_ids = {item.get("vehicle_id") for item in transports if item.get("vehicle_id")}
    if summary["in_transit_transports"]:
        activity_status = "In Transit"
    elif summary["active_transports"]:
        activity_status = "Active"
    elif summary["total_transports"]:
        activity_status = "Completed"
    else:
        activity_status = "No activity"
    return {
        **(document_to_dict(site) or {}),
        **summary,
        "total_vehicles": len(vehicle_ids),
        "activity_status": activity_status,
    }


def list_site_summaries():
    from services.common import collection

    sites = [document_to_dict(site) for site in collection("construction_sites").find({})]
    transports_by_site = defaultdict(list)
    for transport in collection("transport_records").find({}):
        transports_by_site[transport.get("site_id")].append(transport)
    return [_site_summary(site, transports_by_site.get(site.get("site_id"), [])) for site in sites]


def get_site_summary(site_id):
    from services.common import collection

    site = document_to_dict(collection("construction_sites").find_one({"site_id": site_id}))
    if not site:
        return None
    transports = list(collection("transport_records").find({"site_id": site_id}))
    return _site_summary(site, transports)


def list_site_vehicle_summaries(site_id):
    from services.common import collection

    site = document_to_dict(collection("construction_sites").find_one({"site_id": site_id}))
    if not site:
        return None
    transports = list(collection("transport_records").find({"site_id": site_id}))
    transports_by_vehicle = defaultdict(list)
    for transport in transports:
        vehicle_id = transport.get("vehicle_id")
        if vehicle_id:
            transports_by_vehicle[vehicle_id].append(transport)

    vehicles = []
    for vehicle_id, vehicle_transports in sorted(transports_by_vehicle.items()):
        vehicle = document_to_dict(collection("vehicles").find_one({"vehicle_id": vehicle_id}))
        vehicles.append({
            "vehicle_id": vehicle_id,
            "vehicle": vehicle,
            **_summarize_transports(vehicle_transports),
        })
    return vehicles


def list_site_vehicle_transports(site_id, vehicle_id):
    from services.common import collection

    if not collection("construction_sites").find_one({"site_id": site_id}):
        return None
    if not collection("vehicles").find_one({"vehicle_id": vehicle_id}):
        return None

    query = {"site_id": site_id, "vehicle_id": vehicle_id}
    transports = collection("transport_records").find(query).sort("created_at", -1)
    diary = []
    for document in transports:
        transport = document_to_dict(document)
        waste_id = transport.get("waste_id")
        waste = collection("waste_records").find_one({"waste_id": waste_id}) if waste_id else None
        latest_gps = collection("gps_tracking").find_one(
            {"transport_id": transport["transport_id"]}, sort=[("timestamp", -1)]
        )
        transport["expected_weight_kg"] = waste.get("estimated_weight_kg") if waste else None
        transport["latest_gps"] = document_to_dict(latest_gps)
        transport["latest_route_status"] = transport.get(
            "latest_route_status", latest_gps.get("route_status") if latest_gps else None
        )
        diary.append(transport)
    return diary