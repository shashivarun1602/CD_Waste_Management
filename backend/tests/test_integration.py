import sys
import unittest
from pathlib import Path
from uuid import uuid4

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from config import Config


class CompleteWorkflowIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=1500)
        cls.database = cls.client[Config.DATABASE_NAME]
        cls.database.command("ping")
        cls.api = app.test_client()
        cls.suffix = uuid4().hex[:8]
        cls.created = {"construction_sites": [], "vehicles": [], "drivers": [], "facilities": [], "waste_records": [], "transport_records": [], "gps_tracking": []}

    @classmethod
    def tearDownClass(cls):
        for collection_name, identifiers in cls.created.items():
            if identifiers:
                field = {
                    "construction_sites": "site_id",
                    "vehicles": "vehicle_id",
                    "drivers": "driver_id",
                    "facilities": "facility_id",
                    "waste_records": "waste_id",
                    "transport_records": "transport_id",
                    "gps_tracking": "tracking_id",
                }[collection_name]
                cls.database[collection_name].delete_many({field: {"$in": identifiers}})
        cls.client.close()

    def create(self, path, payload, collection, field):
        response = self.api.post(path, json=payload)
        self.assertEqual(response.status_code, 201, response.get_json())
        document = response.get_json()["data"]
        self.created[collection].append(document[field])
        return document

    def test_complete_chain_of_custody_workflow(self):
        site = self.create("/api/sites", {"name": f"Integration Site {self.suffix}", "address": "Hyderabad"}, "construction_sites", "site_id")
        vehicle = self.create("/api/vehicles", {"registration_number": f"TS09IT{self.suffix}", "vehicle_type": "Tipper Truck", "capacity_kg": 10000}, "vehicles", "vehicle_id")
        driver = self.create("/api/drivers", {"name": f"Integration Driver {self.suffix}", "license_number": f"LIC-{self.suffix}"}, "drivers", "driver_id")
        facility = self.create("/api/facilities", {"name": f"Integration Recycling {self.suffix}", "facility_type": "Recycling", "address": "Hyderabad", "authorized": True}, "facilities", "facility_id")
        waste = self.create("/api/waste", {"site_id": site["site_id"], "waste_type": "Concrete", "estimated_weight_kg": 2500}, "waste_records", "waste_id")
        transport = self.create("/api/transports", {"site_id": site["site_id"], "vehicle_id": vehicle["vehicle_id"], "driver_id": driver["driver_id"], "facility_id": facility["facility_id"], "waste_id": waste["waste_id"]}, "transport_records", "transport_id")
        transport_id = transport["transport_id"]

        self.assertEqual(self.api.post(f"/api/transports/{transport_id}/load", json={"weight_kg": 2500, "source": "manual"}).status_code, 200)
        self.assertEqual(self.api.post(f"/api/transports/{transport_id}/start", json={}).status_code, 200)
        gps = self.api.post("/api/gps", json={"transport_id": transport_id, "latitude": 17.385, "longitude": 78.4867, "speed_kmph": 35, "source": "manual"})
        self.assertEqual(gps.status_code, 201, gps.get_json())
        self.created["gps_tracking"].append(gps.get_json()["data"]["tracking_id"])
        self.assertEqual(self.api.post(f"/api/transports/{transport_id}/arrive", json={"received_weight_kg": 2475, "source": "manual"}).status_code, 200)
        verified = self.api.post(f"/api/transports/{transport_id}/verify", json={})
        self.assertEqual(verified.status_code, 200, verified.get_json())
        self.assertEqual(verified.get_json()["data"]["weight_status"], "Verified")
        completed = self.api.post(f"/api/transports/{transport_id}/complete", json={})
        self.assertEqual(completed.status_code, 200, completed.get_json())
        self.assertEqual(completed.get_json()["data"]["status"], "Completed")


if __name__ == "__main__":
    unittest.main()
