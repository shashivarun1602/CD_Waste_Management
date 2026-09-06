from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from db import get_database
from utils.id_generator import generate_id
from utils.response import document_to_dict


def now():
    return datetime.now(timezone.utc).isoformat()


def collection(name):
    return get_database()[name]


def list_documents(name, query=None, sort_field=None):
    cursor = collection(name).find(query or {})
    if sort_field:
        cursor = cursor.sort(sort_field, -1)
    return [document_to_dict(item) for item in cursor]


def get_document(name, identifier_field, identifier):
    return document_to_dict(collection(name).find_one({identifier_field: identifier}))


def create_document(name, identifier_field, prefix, data):
    timestamp = now()
    document = dict(data)
    document[identifier_field] = generate_id(prefix)
    document["created_at"] = timestamp
    document["updated_at"] = timestamp
    collection(name).insert_one(document)
    return document_to_dict(document)


def update_document(name, identifier_field, identifier, updates):
    updates = {key: value for key, value in updates.items() if key not in {"_id", identifier_field, "created_at"}}
    updates["updated_at"] = now()
    result = collection(name).find_one_and_update(
        {identifier_field: identifier}, {"$set": updates}, return_document=ReturnDocument.AFTER
    )
    return document_to_dict(result)


def soft_delete(name, identifier_field, identifier):
    return update_document(name, identifier_field, identifier, {"status": "Inactive"})


__all__ = ["DuplicateKeyError", "collection", "create_document", "get_document", "list_documents", "now", "soft_delete", "update_document"]
