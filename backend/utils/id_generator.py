from pymongo import ReturnDocument

from db import get_database


def generate_id(prefix):
    sequence = get_database().counters.find_one_and_update(
        {"_id": prefix},
        {"$inc": {"value": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return f"{prefix}-{sequence['value']:04d}"
