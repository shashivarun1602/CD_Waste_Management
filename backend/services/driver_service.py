from services.common import create_document, get_document, list_documents, soft_delete, update_document

COLLECTION = "drivers"
FIELD = "driver_id"


def list_drivers():
    return list_documents(COLLECTION, sort_field="created_at")


def get_driver(driver_id):
    return get_document(COLLECTION, FIELD, driver_id)


def create_driver(data):
    data.setdefault("status", "Available")
    return create_document(COLLECTION, FIELD, "DRV", data)


def update_driver(driver_id, data):
    return update_document(COLLECTION, FIELD, driver_id, data)


def deactivate_driver(driver_id):
    return soft_delete(COLLECTION, FIELD, driver_id)
