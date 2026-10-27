import sys
sys.path.insert(0, "backend")

from config import Config
from pymongo import MongoClient

client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=10000)
db = client[Config.DATABASE_NAME]

try:
    for name in db.list_collection_names():
        record = db[name].find_one({
            "transport_id": "TRN-0115"
        })

        if record and name != "weight_readings":
            print("\nCollection:", name)
            for key, value in record.items():
                if key != "_id":
                    print(f"{key}: {value}")
finally:
    client.close()
