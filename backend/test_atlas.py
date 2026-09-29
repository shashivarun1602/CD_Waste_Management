import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

uri = os.getenv("MONGO_URI")

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)

    client.admin.command("ping")

    print("MongoDB Atlas connection successful!")

except Exception as e:
    print("MongoDB Atlas connection failed:")
    print(e)