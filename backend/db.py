from pymongo import ASCENDING, DESCENDING, MongoClient

from config import Config

_client = None
_database = None

COLLECTIONS = (
    "construction_sites",
    "vehicles",
    "drivers",
    "facilities",
    "waste_records",
    "transport_records",
    "gps_tracking",
    "counters",
)


def get_database():
    global _client, _database
    if _database is None:
        _client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=1500)
        _database = _client[Config.DATABASE_NAME]
    return _database


def init_db():
    database = get_database()
    indexes = {
        "construction_sites": [("site_id", ASCENDING), ("status", ASCENDING)],
        "vehicles": [("vehicle_id", ASCENDING), ("registration_number", ASCENDING), ("status", ASCENDING)],
        "drivers": [("driver_id", ASCENDING), ("license_number", ASCENDING)],
        "facilities": [("facility_id", ASCENDING), ("status", ASCENDING)],
        "waste_records": [("waste_id", ASCENDING), ("site_id", ASCENDING)],
        "transport_records": [("transport_id", ASCENDING), ("site_id", ASCENDING), ("vehicle_id", ASCENDING), ("driver_id", ASCENDING), ("facility_id", ASCENDING), ("status", ASCENDING)],
        "gps_tracking": [("transport_id", ASCENDING), ("vehicle_id", ASCENDING), ("timestamp", DESCENDING)],
    }
    try:
        for collection_name, fields in indexes.items():
            collection = database[collection_name]
            for field, direction in fields:
                collection.create_index([(field, direction)], unique=field.endswith("_id") and field not in {"site_id", "vehicle_id", "driver_id", "facility_id"})
        database.vehicles.create_index("registration_number", unique=True)
        database.drivers.create_index("license_number", unique=True, sparse=True)
        database.counters.create_index("_id", unique=True)
    except Exception:
        # MongoDB may be offline during frontend-only development; connect lazily on request.
        pass
