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
    "devices",
    "weight_readings",
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
        "devices": [("device_id", ASCENDING), ("vehicle_id", ASCENDING), ("status", ASCENDING)],
        "weight_readings": [("transport_id", ASCENDING), ("vehicle_id", ASCENDING), ("device_id", ASCENDING), ("timestamp", DESCENDING)],
    }
    try:
        try:
            database.gps_tracking.drop_index("transport_id_1")
        except Exception:
            pass
        for collection_name, fields in indexes.items():
            collection = database[collection_name]
            for field, direction in fields:
                unique = (collection_name, field) in {
                    ("construction_sites", "site_id"),
                    ("vehicles", "vehicle_id"),
                    ("drivers", "driver_id"),
                    ("facilities", "facility_id"),
                    ("waste_records", "waste_id"),
                    ("transport_records", "transport_id"),
                    ("devices", "device_id"),
                }
                collection.create_index([(field, direction)], unique=unique)
        database.vehicles.create_index("registration_number", unique=True)
        database.drivers.create_index("license_number", unique=True, sparse=True)
        database.devices.create_index("device_id", unique=True)
        database.counters.create_index("_id", unique=True)
    except Exception:
        # MongoDB may be offline during frontend-only development; connect lazily on request.
        pass
