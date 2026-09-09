from services.common import collection, create_document, get_document, list_documents, soft_delete, update_document
from services.route_service import haversine_meters

COLLECTION = "facilities"
FIELD = "facility_id"


def list_facilities():
    return list_documents(COLLECTION, sort_field="created_at")


def get_facility(facility_id):
    return get_document(COLLECTION, FIELD, facility_id)


def create_facility(data):
    data = dict(data)
    data.setdefault("authorized", False)
    data.setdefault("status", "Active")
    data.setdefault("authorized_waste_types", [])
    return create_document(COLLECTION, FIELD, "FAC", data)


def update_facility(facility_id, data):
    return update_document(COLLECTION, FIELD, facility_id, data)


def deactivate_facility(facility_id):
    return soft_delete(COLLECTION, FIELD, facility_id)


def recommend_facility(waste_type, latitude, longitude):
    candidates = collection(COLLECTION).find({"status": "Active", "authorized": True})
    normalized_type = str(waste_type or "").strip().lower()
    recommendations = []
    for facility in candidates:
        facility_types = [str(value).strip().lower() for value in facility.get("authorized_waste_types", [])]
        if facility_types and normalized_type not in facility_types and "mixed c&d" not in facility_types and "mixed_cnd" not in facility_types:
            continue
        if facility.get("latitude") is None or facility.get("longitude") is None:
            continue
        distance = haversine_meters(latitude, longitude, float(facility["latitude"]), float(facility["longitude"]))
        recommendations.append({
            "facility_id": facility["facility_id"],
            "name": facility.get("name"),
            "distance_meters": round(distance, 2),
            "latitude": facility["latitude"],
            "longitude": facility["longitude"],
            "waste_type": waste_type,
        })
    return sorted(recommendations, key=lambda item: item["distance_meters"])
