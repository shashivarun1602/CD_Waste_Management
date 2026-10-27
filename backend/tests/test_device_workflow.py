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
        cls.device_token = "integration-device-token"
        app.config["DEVICE_API_TOKEN"] = cls.device_token
        cls.client = MongoClient(Config.MONGO_URI, serverSelectionTimeoutMS=1500)
        cls.database = cls.client[Config.DATABASE_NAME]
        cls.database.command("ping")
        cls.api = app.test_client()
        cls.suffix = uuid4().hex[:8]
        cls.created = {name: [] for name in ("construction_sites", "vehicles", "drivers", "facilities", "waste_records", "transport_records", "devices", "device_assignments", "gps_tracking", "weight_readings")}

    @classmethod
    def tearDownClass(cls):
        fields = {
            "construction_sites": "site_id", "vehicles": "vehicle_id", "drivers": "driver_id",
            "facilities": "facility_id", "waste_records": "waste_id", "transport_records": "transport_id",
            "devices": "device_id", "gps_tracking": "tracking_id", "weight_readings": "reading_id",
            "device_assignments": "_id",
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

    def post_device(self, path, payload):
        return self.api.post(path, json=payload, headers={"X-Device-Token": self.device_token})

    def setUp(self):
        self.suffix = uuid4().hex[:8]
        site = self.create("/api/sites", {"name": f"Device Site {self.suffix}", "address": "Hyderabad"}, "construction_sites", "site_id")
        vehicle = self.create("/api/vehicles", {"registration_number": f"TS09DV{self.suffix}", "vehicle_type": "Tipper", "capacity_kg": 10000}, "vehicles", "vehicle_id")
        driver = self.create("/api/drivers", {"name": f"Device Driver {self.suffix}", "license_number": f"DV-{self.suffix}"}, "drivers", "driver_id")
        facility = self.create("/api/facilities", {"name": f"Device Facility {self.suffix}", "facility_type": "Recycling", "address": "Hyderabad", "authorized": True, "authorized_waste_types": ["Concrete"], "latitude": 17.4, "longitude": 78.5}, "facilities", "facility_id")
        waste = self.create("/api/waste", {"site_id": site["site_id"], "waste_type": "Concrete", "estimated_weight_kg": 2500}, "waste_records", "waste_id")
        device = self.create("/api/devices", {"device_id": f"DEV-{self.suffix}", "vehicle_id": vehicle["vehicle_id"]}, "devices", "device_id")
        self.created["device_assignments"].extend([
            f"device:{device['device_id']}",
            f"vehicle:{vehicle['vehicle_id']}",
        ])
        transport = self.create("/api/transports", {"site_id": site["site_id"], "vehicle_id": vehicle["vehicle_id"], "driver_id": driver["driver_id"], "facility_id": facility["facility_id"], "waste_id": waste["waste_id"]}, "transport_records", "transport_id")
        self.device, self.vehicle, self.transport = device, vehicle, transport

    def test_device_gps_resolves_vehicle_transport_and_stores_fix(self):
        response = self.post_device("/api/device/gps", {"device_id": self.device["device_id"], "latitude": 17.385, "longitude": 78.4867, "satellites": 9, "gps_fix": True})
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()["data"]
        self.assertEqual(data["vehicle_id"], self.vehicle["vehicle_id"])
        self.assertEqual(data["transport_id"], self.transport["transport_id"])
        self.assertEqual(data["route_status"], "ON_ROUTE")
        self.assertEqual(data["satellites"], 9)
        self.assertTrue(data["gps_fix"])
        stored = self.database.gps_tracking.find_one({"transport_id": self.transport["transport_id"]})
        self.assertEqual(stored["source"], "device")
        self.assertEqual(stored["latitude"], 17.385)

    def test_unknown_and_inactive_devices_are_rejected(self):
        unknown = self.post_device("/api/device/gps", {"device_id": "DEV-DOES-NOT-EXIST", "latitude": 17, "longitude": 78})
        self.assertEqual(unknown.status_code, 404)
        self.database.devices.update_one({"device_id": self.device["device_id"]}, {"$set": {"status": "inactive"}})
        inactive = self.post_device("/api/device/gps", {"device_id": self.device["device_id"], "latitude": 17, "longitude": 78})
        self.assertEqual(inactive.status_code, 400)

    def test_calibrated_sensor_reading_does_not_set_official_transport_weight(self):
        response = self.post_device("/api/device/weight", {"device_id": self.device["device_id"], "weight_kg": 8420})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["data"]["transport_id"], self.transport["transport_id"])
        reading = self.database.weight_readings.find_one({"transport_id": self.transport["transport_id"]})
        self.assertEqual(reading["weight_kg"], 8420)
        transport = self.database.transport_records.find_one({"transport_id": self.transport["transport_id"]})
        self.assertEqual(transport["status"], "Created")
        self.assertIsNone(transport["loaded_weight_kg"])

    def test_raw_weight_is_stored_without_becoming_kilograms(self):
        response = self.post_device("/api/device/weight", {"device_id": self.device["device_id"], "raw_value": -209177, "calibration_status": "NOT_SET", "weight_kg": None})
        self.assertEqual(response.status_code, 200, response.get_json())
        reading = self.database.weight_readings.find_one({"transport_id": self.transport["transport_id"]})
        self.assertEqual(reading["raw_value"], -209177)
        self.assertEqual(reading["calibration_status"], "NOT_SET")
        self.assertIsNone(reading["weight_kg"])
        transport = self.database.transport_records.find_one({"transport_id": self.transport["transport_id"]})
        self.assertEqual(transport["status"], "Created")
        self.assertIsNone(transport["loaded_weight_kg"])

    def test_transport_for_another_vehicle_is_rejected(self):
        self.database.transport_records.update_one({"transport_id": self.transport["transport_id"]}, {"$set": {"vehicle_id": "VEH-OTHER"}})
        response = self.post_device("/api/device/gps", {"device_id": self.device["device_id"], "latitude": 17.385, "longitude": 78.4867})
        self.assertEqual(response.status_code, 400, response.get_json())

    def test_device_rejects_when_no_active_transport_exists(self):
        self.database.transport_records.update_one({"transport_id": self.transport["transport_id"]}, {"$set": {"status": "Completed"}})
        gps = self.post_device("/api/device/gps", {"device_id": self.device["device_id"], "latitude": 17.385, "longitude": 78.4867})
        self.assertEqual(gps.status_code, 404, gps.get_json())
        self.assertEqual(self.database.gps_tracking.count_documents({"device_id": self.device["device_id"]}), 0)
        weight = self.post_device("/api/device/weight", {"device_id": self.device["device_id"], "weight_kg": 8420})
        self.assertEqual(weight.status_code, 404, weight.get_json())
        self.assertEqual(self.database.weight_readings.count_documents({"device_id": self.device["device_id"]}), 0)

    def test_multiple_active_transports_are_rejected_as_ambiguous(self):
        second = {
            "transport_id": f"TRN-AMBIG-{self.suffix}", "site_id": self.transport["site_id"],
            "vehicle_id": self.vehicle["vehicle_id"], "driver_id": self.transport["driver_id"],
            "facility_id": self.transport["facility_id"], "waste_id": self.transport["waste_id"],
            "status": "Created", "source": "manual", "created_at": self.transport["created_at"],
            "updated_at": self.transport["updated_at"],
        }
        self.database.transport_records.insert_one(second)
        self.created["transport_records"].append(second["transport_id"])
        gps = self.post_device("/api/device/gps", {"device_id": self.device["device_id"], "latitude": 17.385, "longitude": 78.4867})
        self.assertEqual(gps.status_code, 400, gps.get_json())
        self.assertIn("Multiple active transports", gps.get_json()["message"])

    def test_new_active_transport_is_used_after_old_trip_completes(self):
        self.database.transport_records.update_one({"transport_id": self.transport["transport_id"]}, {"$set": {"status": "Completed"}})
        new_transport = {
            "transport_id": f"TRN-NEW-{self.suffix}", "site_id": self.transport["site_id"],
            "vehicle_id": self.vehicle["vehicle_id"], "driver_id": self.transport["driver_id"],
            "facility_id": self.transport["facility_id"], "waste_id": self.transport["waste_id"],
            "status": "Created", "source": "manual", "created_at": self.transport["created_at"],
            "updated_at": self.transport["updated_at"],
        }
        self.database.transport_records.insert_one(new_transport)
        self.created["transport_records"].append(new_transport["transport_id"])
        self.database.vehicles.update_one(
            {"vehicle_id": self.vehicle["vehicle_id"]},
            {"$set": {"active_transport_id": new_transport["transport_id"]}},
        )
        response = self.post_device("/api/device/gps", {"device_id": self.device["device_id"], "latitude": 17.385, "longitude": 78.4867})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["data"]["transport_id"], new_transport["transport_id"])

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
        first = self.post_device("/api/device/gps", {"device_id": self.device["device_id"], "latitude": 17.385, "longitude": 78.4867})
        self.assertEqual(first.status_code, 200)
        second = self.post_device("/api/device/gps", {"device_id": self.device["device_id"], "latitude": 17.42, "longitude": 78.45})
        self.assertEqual(second.status_code, 200, second.get_json())
        self.assertEqual(second.get_json()["data"]["route_status"], "DEVIATION")


if __name__ == "__main__":
    unittest.main()