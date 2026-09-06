from services.common import create_document, get_document, list_documents, soft_delete, update_document

COLLECTION = "vehicles"
FIELD = "vehicle_id"


def list_vehicles():
    return list_documents(COLLECTION, sort_field="created_at")


def get_vehicle(vehicle_id):
    return get_document(COLLECTION, FIELD, vehicle_id)


def create_vehicle(data):
    data.setdefault("status", "Available")
    data.setdefault("current_site_id", None)
    return create_document(COLLECTION, FIELD, "VEH", data)


def update_vehicle(vehicle_id, data):
    return update_document(COLLECTION, FIELD, vehicle_id, data)


def deactivate_vehicle(vehicle_id):
    return soft_delete(COLLECTION, FIELD, vehicle_id)
