from services.common import create_document, get_document, list_documents, soft_delete, update_document

COLLECTION = "construction_sites"
FIELD = "site_id"


def list_sites():
    return list_documents(COLLECTION, sort_field="created_at")


def get_site(site_id):
    return get_document(COLLECTION, FIELD, site_id)


def create_site(data):
    data.setdefault("status", "Active")
    return create_document(COLLECTION, FIELD, "CON", data)


def update_site(site_id, data):
    return update_document(COLLECTION, FIELD, site_id, data)


def deactivate_site(site_id):
    return soft_delete(COLLECTION, FIELD, site_id)
