from services.common import create_document, get_document, list_documents, soft_delete, update_document

COLLECTION = "waste_records"
FIELD = "waste_id"


def list_waste():
    return list_documents(COLLECTION, sort_field="created_at")


def get_waste(waste_id):
    return get_document(COLLECTION, FIELD, waste_id)


def create_waste(data):
    data.setdefault("weight_source", data.get("source", "manual"))
    return create_document(COLLECTION, FIELD, "WST", data)


def update_waste(waste_id, data):
    return update_document(COLLECTION, FIELD, waste_id, data)


def delete_waste(waste_id):
    return soft_delete(COLLECTION, FIELD, waste_id)
