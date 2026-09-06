from services.common import create_document, get_document, list_documents, soft_delete, update_document

COLLECTION = "facilities"
FIELD = "facility_id"


def list_facilities():
    return list_documents(COLLECTION, sort_field="created_at")


def get_facility(facility_id):
    return get_document(COLLECTION, FIELD, facility_id)


def create_facility(data):
    data.setdefault("authorized", False)
    data.setdefault("status", "Active")
    return create_document(COLLECTION, FIELD, "FAC", data)


def update_facility(facility_id, data):
    return update_document(COLLECTION, FIELD, facility_id, data)


def deactivate_facility(facility_id):
    return soft_delete(COLLECTION, FIELD, facility_id)
