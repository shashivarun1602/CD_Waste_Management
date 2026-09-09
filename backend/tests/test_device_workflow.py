import sys
import unittest
from pathlib import Path
from uuid import uuid4

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from config import Config


class DeviceWorkflowIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=1500)
        cls.database = cls.client[Config.DATABASE_NAME]
        cls.database.command("ping")
        cls.api = app.test_client()
        cls.suffix = uuid4().hex[:8]
        cls.created = {name: [] for name in ("construction_sites", "vehicles", "drivers", "facilities", "waste_records", "transport_records", "devices", "gps_tracking", "weight_readings")}

    @classmethod
    def tearDownClass(cls):
        fields = {
            "construction_sites": "site_id", "vehicles": "vehicle_id", "drivers": "driver_id",
            "facilities": "facility_id", "waste_records": "waste_id", "transport_records": "transport_id",
            "devices": "device_id", "gps_tracking": "tracking_id", "weight_readings": "reading_id",
        }
        for collection_name, identifiers in cls.created.items():
            if identifiers:
                cls.database[collection_name].delete_many({fields[collection_name]: {"$in": identifiers}})
        cls.client.close()

    def create(self, path, payload, collection, field):
        response = self.api.post(path, json=payload)
        self.assertEqual(response.status_code, 201, response.get_json())
        document = response.get_json()["data"]
        self.created[collection].append(document[field])
        return document

    def setUp(self):
        site = self.create("/api/sites", {"name": f"Device Site {self.suffix}", "address": "Hyderabad"}, "construction_sites", "site_id")
        vehicle = self.create("/api/vehicles", {"registration_number": f"TS09DV{self.suffix}", "vehicle_type": "Tipper", "capacity_kg": 10000}, "vehicles", "vehicle_id")
        driver = self.create("/api/drivers", {"name": f"Device Driver {self.suffix}", "license_number": f"DV-{self.suffix}"}, "drivers", "driver_id")
        facility = self.create("/api/facilities", {"name": f"Device Facility {self.suffix}", "facility_type": "Recycling", "address": "Hyderabad", "authorized": True, "authorized_waste_types": ["Concrete"], "latitude": 17.4, "longitude": 78.5}, "facilities", "facility_id")
        waste = self.create("/api/waste", {"site_id": site["site_id"], "waste_type": "Concrete", "estimated_weight_kg": 2500}, "waste_records", "waste_id")
        device = self.create("/api/devices", {"vehicle_id": vehicle["vehicle_id"]}, "devices", "device_id")
        transport = self.create("/api/transports", {"site_id": site["site_id"], "vehicle_id": vehicle["vehicle_id"], "driver_id": driver["driver_id"], "facility_id": facility["facility_id"], "waste_id": waste["waste_id"]}, "transport_records", "transport_id")
        self.device, self.vehicle, self.transport = device, vehicle, transport

    def test_device_gps_resolves_vehicle_and_transport(self):
        response = self.api.post("/api/device/gps", json={"device_id": self.device["device_id"], "latitude": 17.385, "longitude": 78.4867})
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()["data"]
        self.assertEqual(data["vehicle_id"], self.vehicle["vehicle_id"])
        self.assertEqual(data["transport_id"], self.transport["transport_id"])
        self.assertEqual(data["route_status"], "ON_ROUTE")
        self.assertEqual(self.database.gps_tracking.count_documents({"transport_id": self.transport["transport_id"]}), 1)

    def test_invalid_inactive_and_unassigned_devices_are_rejected(self):
        invalid = self.api.post("/api/device/gps", json={"device_id": "ESP-DOES-NOT-EXIST", "latitude": 17, "longitude": 78})
        self.assertEqual(invalid.status_code, 404)
        self.database.devices.update_one({"device_id": self.device["device_id"]}, {"$set": {"status": "inactive"}})
        inactive = self.api.post("/api/device/gps", json={"device_id": self.device["device_id"], "latitude": 17, "longitude": 78})
        self.assertEqual(inactive.status_code, 400)

    def test_weight_is_routed_and_preserved_as_history(self):
        response = self.api.post("/api/device/weight", json={"device_id": self.device["device_id"], "weight_kg": 8420})
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()["data"]
        self.assertEqual(data["transport_id"], self.transport["transport_id"])
        self.assertEqual(self.database.weight_readings.count_documents({"transport_id": self.transport["transport_id"]}), 1)
        transport = self.database.transport_records.find_one({"transport_id": self.transport["transport_id"]})
        self.assertEqual(transport["loaded_weight_kg"], 8420)

    def test_recommendation_excludes_unauthorized_and_inactive_facilities(self):
        self.create("/api/facilities", {"name": f"Wrong Type {self.suffix}", "facility_type": "Processing", "address": "Hyderabad", "authorized": True, "authorized_waste_types": ["Metal"], "latitude": 17.386, "longitude": 78.487}, "facilities", "facility_id")
        inactive = self.create("/api/facilities", {"name": f"Inactive {self.suffix}", "facility_type": "Recycling", "address": "Hyderabad", "authorized": True, "authorized_waste_types": ["Concrete"], "latitude": 17.386, "longitude": 78.487}, "facilities", "facility_id")
        self.database.facilities.update_one({"facility_id": inactive["facility_id"]}, {"$set": {"status": "Inactive"}})
        response = self.api.get("/api/facilities/recommend?waste_type=Concrete&latitude=17.385&longitude=78.4867")
        self.assertEqual(response.status_code, 200, response.get_json())
        identifiers = {item["facility_id"] for item in response.get_json()["data"]}
        self.assertIn(self.transport["facility_id"], identifiers)
        self.assertNotIn(inactive["facility_id"], identifiers)

    def test_deviation_is_recorded_against_same_transport(self):
        first = self.api.post("/api/device/gps", json={"device_id": self.device["device_id"], "latitude": 17.385, "longitude": 78.4867})
        self.assertEqual(first.status_code, 200)
        second = self.api.post("/api/device/gps", json={"device_id": self.device["device_id"], "latitude": 17.42, "longitude": 78.45})
        self.assertEqual(second.status_code, 200, second.get_json())
        self.assertEqual(second.get_json()["data"]["route_status"], "DEVIATION")


if __name__ == "__main__":
    unittest.main()