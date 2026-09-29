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

    def test_transport_creation_does_not_require_waste_id_or_driver_id(self):
        site = self.create("/api/sites", {"name": f"Optional Waste Site {self.suffix}", "address": "Hyderabad"}, "construction_sites", "site_id")
        vehicle = self.create("/api/vehicles", {"registration_number": f"TS09NW{self.suffix}", "vehicle_type": "Tipper Truck", "capacity_kg": 10000}, "vehicles", "vehicle_id")
        facility = self.create("/api/facilities", {"name": f"Optional Waste Facility {self.suffix}", "facility_type": "Recycling", "address": "Hyderabad", "authorized": True}, "facilities", "facility_id")

        transport = self.create("/api/transports", {
            "site_id": site["site_id"],
            "vehicle_id": vehicle["vehicle_id"],
            "facility_id": facility["facility_id"],
        }, "transport_records", "transport_id")

        stored = self.database.transport_records.find_one({"transport_id": transport["transport_id"]})
        self.assertNotIn("waste_id", stored)
        self.assertNotIn("driver_id", stored)

    def test_reused_vehicle_history_stays_scoped_to_site(self):
        site_a = self.create("/api/sites", {"name": f"Reuse Site A {self.suffix}", "address": "Site A"}, "construction_sites", "site_id")
        site_b = self.create("/api/sites", {"name": f"Reuse Site B {self.suffix}", "address": "Site B"}, "construction_sites", "site_id")
        vehicle = self.create("/api/vehicles", {"registration_number": f"TS09RV{self.suffix}", "vehicle_type": "Tipper Truck", "capacity_kg": 10000}, "vehicles", "vehicle_id")
        facility = self.create("/api/facilities", {"name": f"Reuse Facility {self.suffix}", "facility_type": "Recycling", "address": "Facility", "authorized": True}, "facilities", "facility_id")

        def complete_trip(site, loaded_weight):
            transport = self.create("/api/transports", {
                "site_id": site["site_id"],
                "vehicle_id": vehicle["vehicle_id"],
                "facility_id": facility["facility_id"],
            }, "transport_records", "transport_id")
            transport_id = transport["transport_id"]
            self.assertEqual(self.api.post(f"/api/transports/{transport_id}/load", json={"weight_kg": loaded_weight}).status_code, 200)
            self.assertEqual(self.api.post(f"/api/transports/{transport_id}/start", json={}).status_code, 200)
            self.assertEqual(self.api.post(f"/api/transports/{transport_id}/arrive", json={"received_weight_kg": loaded_weight}).status_code, 200)
            self.assertEqual(self.api.post(f"/api/transports/{transport_id}/verify", json={}).status_code, 200)
            self.assertEqual(self.api.post(f"/api/transports/{transport_id}/complete", json={}).status_code, 200)
            return transport_id

        trip_a1 = complete_trip(site_a, 1000)
        trip_a2 = complete_trip(site_a, 1200)
        trip_b1 = complete_trip(site_b, 800)

        all_sites = self.api.get("/api/dashboard/sites").get_json()["data"]
        all_sites_by_id = {site_summary["site_id"]: site_summary for site_summary in all_sites}
        self.assertEqual(all_sites_by_id[site_a["site_id"]]["total_transports"], 2)
        self.assertEqual(all_sites_by_id[site_b["site_id"]]["total_transports"], 1)
        site_a_summary = self.api.get(f"/api/dashboard/sites/{site_a['site_id']}").get_json()["data"]
        site_b_summary = self.api.get(f"/api/dashboard/sites/{site_b['site_id']}").get_json()["data"]
        self.assertEqual(site_a_summary["total_transports"], 2)
        self.assertEqual(site_a_summary["total_loaded_weight_kg"], 2200)
        self.assertEqual(site_a_summary["completed_transports"], 2)
        self.assertEqual(site_b_summary["total_transports"], 1)
        self.assertEqual(site_b_summary["total_loaded_weight_kg"], 800)

        site_a_vehicles = self.api.get(f"/api/dashboard/sites/{site_a['site_id']}/vehicles").get_json()["data"]
        self.assertEqual([item["vehicle_id"] for item in site_a_vehicles], [vehicle["vehicle_id"]])
        site_a_diary = self.api.get(f"/api/dashboard/sites/{site_a['site_id']}/vehicles/{vehicle['vehicle_id']}/transports").get_json()["data"]
        site_b_diary = self.api.get(f"/api/dashboard/sites/{site_b['site_id']}/vehicles/{vehicle['vehicle_id']}/transports").get_json()["data"]
        self.assertEqual({item["transport_id"] for item in site_a_diary}, {trip_a1, trip_a2})
        self.assertEqual({item["transport_id"] for item in site_b_diary}, {trip_b1})
        self.assertTrue(all(item["site_id"] == site_a["site_id"] for item in site_a_diary))
        self.assertTrue(all(item["site_id"] == site_b["site_id"] for item in site_b_diary))


if __name__ == "__main__":
    unittest.main()
