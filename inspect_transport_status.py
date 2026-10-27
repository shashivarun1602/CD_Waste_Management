import sys
sys.path.insert(0, "backend")
from config import Config
from pymongo import MongoClient

client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=10000)
try:
    db = client[Config.DATABASE_NAME]
    record = db["transport_records"].find_one(
        {"transport_id": "TRN-0115"},
        {"_id": 0}
    )
    print(record)
finally:
    client.close()
