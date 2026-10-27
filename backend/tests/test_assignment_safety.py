import sys
import threading
import unittest
from copy import deepcopy
from itertools import count
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from routes.vehicles import vehicles_bp
from services import device_service, transport_service, vehicle_service
from services import weight_service
from services.dashboard_service import list_site_summaries


def matches(document, query):
    for field, expected in query.items():
        if field == "$or":
            if not any(matches(document, clause) for clause in expected):
                return False
            continue
        if field == "$and":
            if not all(matches(document, clause) for clause in expected):
                return False
            continue

        value = document.get(field)
        if isinstance(expected, dict) and any(key.startswith("$") for key in expected):
            for operator, operand in expected.items():
                if operator == "$exists" and ((field in document) != operand):
                    return False
                if operator == "$in" and value not in operand:
                    return False
                if operator == "$ne" and value == operand:
                    return False
        elif value != expected and not (expected is None and field not in document):
            return False
    return True


def apply_update(document, update):
    for field, value in update.get("$set", {}).items():
        document[field] = value
    for field in update.get("$unset", {}):
        document.pop(field, None)


class MemoryCollection:
    def __init__(self, documents=None):
        self.documents = deepcopy(documents or [])
        self.lock = threading.RLock()
        self.find_barrier = None

    def find_one(self, query, *args, **kwargs):
        if self.find_barrier and isinstance(query.get("status"), dict) and "$in" in query["status"]:
            self.find_barrier.wait(timeout=5)
        with self.lock:
            return deepcopy(next((item for item in self.documents if matches(item, query)), None))

    def find(self, query):
        with self.lock:
            return MemoryCursor([item for item in self.documents if matches(item, query)])

    def find_one_and_update(self, query, update, return_document=ReturnDocument.BEFORE):
        with self.lock:
            document = next((item for item in self.documents if matches(item, query)), None)
            if document is None:
                return None
            before = deepcopy(document)
            apply_update(document, update)
            return deepcopy(document if return_document == ReturnDocument.AFTER else before)

    def update_one(self, query, update):
        with self.lock:
            document = next((item for item in self.documents if matches(item, query)), None)
            if document is None:
                return SimpleNamespace(matched_count=0, modified_count=0)
            apply_update(document, update)
            return SimpleNamespace(matched_count=1, modified_count=1)

    def insert_one(self, document):
        with self.lock:
            if any(item.get("_id") == document.get("_id") for item in self.documents if "_id" in document):
                raise DuplicateKeyError("duplicate _id")
            if self is self.database.devices and any(
                item.get("device_id") == document.get("device_id") for item in self.documents
            ):
                raise DuplicateKeyError("duplicate device_id")
            self.documents.append(deepcopy(document))

    def delete_one(self, query):
        with self.lock:
            index = next((index for index, item in enumerate(self.documents) if matches(item, query)), None)
            if index is not None:
                self.documents.pop(index)
            return SimpleNamespace(deleted_count=int(index is not None))


class MemoryCursor(list):
    def sort(self, field, direction):
        super().sort(key=lambda item: item.get(field, ""), reverse=direction < 0)
        return self


class MemoryDatabase:
    def __init__(self):
        self.collections = {
            "construction_sites": MemoryCollection([
                {"site_id": "CON-A", "name": "Site A", "status": "Active"},
                {"site_id": "CON-B", "name": "Site B", "status": "Active"},
                {"site_id": "CON-INACTIVE", "name": "Inactive", "status": "Inactive"},
            ]),
            "vehicles": MemoryCollection([
                {"vehicle_id": "VEH-1", "registration_number": "TRUCK-001", "status": "Available", "current_site_id": None},
                {"vehicle_id": "VEH-2", "registration_number": "TRUCK-002", "status": "Available", "current_site_id": None},
            ]),
            "facilities": MemoryCollection([
                {"facility_id": "FAC-1", "status": "Active", "authorized": True},
            ]),
            "transport_records": MemoryCollection(),
            "devices": MemoryCollection(),
            "device_assignments": MemoryCollection(),
            "drivers": MemoryCollection(),
            "waste_records": MemoryCollection(),
            "gps_tracking": MemoryCollection(),
            "weight_readings": MemoryCollection(),
        }
        for name, collection in self.collections.items():
            collection.database = self
            setattr(self, name, collection)

    def __getitem__(self, name):
        return self.collections[name]


class AssignmentSafetyTest(unittest.TestCase):
    def setUp(self):
        self.database = MemoryDatabase()
        self.transport_ids = count(1)
        self.patches = [
            patch("services.common.collection", side_effect=self.database.__getitem__),
            patch("services.transport_service.collection", side_effect=self.database.__getitem__),
            patch("services.vehicle_service.collection", side_effect=self.database.__getitem__),
            patch("services.device_service.collection", side_effect=self.database.__getitem__),
            patch("services.weight_service.collection", side_effect=self.database.__getitem__),
            patch("services.transport_service.generate_id", side_effect=lambda prefix: f"{prefix}-{next(self.transport_ids):04d}"),
            patch("services.transport_service.create_document", side_effect=self.create_document),
            patch("services.device_service.create_document", side_effect=self.create_document),
            patch("services.weight_service.create_document", side_effect=self.create_document),
        ]
        for active_patch in self.patches:
            active_patch.start()
            self.addCleanup(active_patch.stop)

    def create_document(self, name, identifier_field, prefix, data, identifier=None):
        document = deepcopy(data)
        document[identifier_field] = identifier or f"{prefix}-TEST"
        document["created_at"] = "2026-10-21T00:00:00+00:00"
        document["updated_at"] = document["created_at"]
        self.database[name].insert_one(document)
        return deepcopy(document)

    def create_transport(self, site_id, vehicle_id="VEH-1"):
        return transport_service.create_transport({
            "site_id": site_id,
            "vehicle_id": vehicle_id,
            "facility_id": "FAC-1",
        })

    def create_mismatched_transport(self):
        device = device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-1"})
        transport = self.create_transport("CON-A")
        self.database.transport_records.update_one(
            {"transport_id": transport["transport_id"]},
            {
                "$set": {
                    "status": "Mismatch",
                    "weight_status": "Mismatch",
                    "loaded_weight_kg": 1000,
                    "received_weight_kg": 800,
                    "weight_difference_kg": 200,
                    "difference_percentage": 20,
                    "verified_at": "2026-10-21T01:00:00+00:00",
                }
            },
        )
        self.database.weight_readings.insert_one({
            "reading_id": "WGT-OLD",
            "transport_id": transport["transport_id"],
            "weight_kg": 1000,
            "timestamp": "2026-10-21T00:30:00+00:00",
        })
        return device, self.database.transport_records.find_one({"transport_id": transport["transport_id"]})

    def complete_verified(self, transport, loaded_weight):
        self.database.transport_records.update_one(
            {"transport_id": transport["transport_id"]},
            {"$set": {"status": "Verified", "weight_status": "Verified", "loaded_weight_kg": loaded_weight}},
        )
        return transport_service.complete_transport(transport["transport_id"])

    def test_reuse_complete_reassign_preserves_history_and_site_totals(self):
        site_a_transports = []
        for loaded_weight in (1000, 1200):
            transport = self.create_transport("CON-A")
            self.complete_verified(transport, loaded_weight)
            site_a_transports.append(transport["transport_id"])
            vehicle = self.database.vehicles.find_one({"vehicle_id": "VEH-1"})
            self.assertEqual(vehicle["status"], "Available")
            self.assertIsNone(vehicle["current_site_id"])
            self.assertNotIn("active_transport_id", vehicle)

        vehicle_service.assign_vehicle_to_site("VEH-1", "CON-B")
        site_b_first = self.create_transport("CON-B")
        self.complete_verified(site_b_first, 800)
        site_b_second = self.create_transport("CON-B")

        for transport_id in site_a_transports:
            historical = self.database.transport_records.find_one({"transport_id": transport_id})
            self.assertEqual(historical["site_id"], "CON-A")
            self.assertEqual(historical["vehicle_id"], "VEH-1")
        self.assertEqual(site_b_first["site_id"], "CON-B")
        self.assertEqual(site_b_second["site_id"], "CON-B")

        with patch("services.common.collection", side_effect=self.database.__getitem__):
            summaries = list_site_summaries()
        summary_by_site = {item["site_id"]: item for item in summaries}
        self.assertEqual(summary_by_site["CON-A"]["total_transports"], 2)
        self.assertEqual(summary_by_site["CON-A"]["total_loaded_weight_kg"], 2200)
        self.assertEqual(summary_by_site["CON-B"]["total_transports"], 2)
        self.assertEqual(summary_by_site["CON-B"]["total_loaded_weight_kg"], 800)

    def test_assignment_rejects_active_transport_and_ineligible_site(self):
        self.create_transport("CON-A")
        with self.assertRaisesRegex(RuntimeError, "active transport"):
            vehicle_service.assign_vehicle_to_site("VEH-1", "CON-B")
        with self.assertRaisesRegex(ValueError, "not active"):
            vehicle_service.assign_vehicle_to_site("VEH-2", "CON-INACTIVE")
        with self.assertRaises(LookupError):
            vehicle_service.assign_vehicle_to_site("VEH-MISSING", "CON-B")
        with self.assertRaises(LookupError):
            vehicle_service.assign_vehicle_to_site("VEH-2", "CON-MISSING")

    def test_assignment_endpoint_accepts_site_id_and_conflicts_when_busy(self):
        app = Flask(__name__)
        app.register_blueprint(vehicles_bp, url_prefix="/api")
        client = app.test_client()

        assigned = client.put("/api/vehicles/VEH-1/site", json={"site_id": "CON-A"})
        self.assertEqual(assigned.status_code, 200)
        self.assertEqual(assigned.get_json()["data"]["current_site_id"], "CON-A")

        self.create_transport("CON-A")
        conflict = client.put("/api/vehicles/VEH-1/site", json={"site_id": "CON-B"})
        self.assertEqual(conflict.status_code, 409)

    def test_device_assignment_is_one_to_one_and_can_be_reassigned(self):
        device = device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-1"})
        with self.assertRaisesRegex(RuntimeError, "already has a device"):
            device_service.create_device({"device_id": "ESP32-LAB-02", "vehicle_id": "VEH-1"})
        with self.assertRaisesRegex(RuntimeError, "already registered"):
            device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-2"})

        reassigned = device_service.update_device(device["device_id"], {"vehicle_id": "VEH-2"})
        vehicle_one = self.database.vehicles.find_one({"vehicle_id": "VEH-1"})
        vehicle_two = self.database.vehicles.find_one({"vehicle_id": "VEH-2"})
        self.assertNotIn("device_id", vehicle_one)
        self.assertEqual(vehicle_two["device_id"], "ESP32-LAB-01")
        self.assertEqual(reassigned["vehicle_id"], "VEH-2")
        self.assertEqual(
            self.database.device_assignments.find_one({"_id": "device:ESP32-LAB-01"})["vehicle_id"],
            "VEH-2",
        )
        self.assertIsNone(self.database.device_assignments.find_one({"_id": "vehicle:VEH-1"}))
        self.assertEqual(
            self.database.device_assignments.find_one({"_id": "vehicle:VEH-2"})["device_id"],
            "ESP32-LAB-01",
        )
        self.assertEqual(len(self.database.device_assignments.documents), 2)
        self.assertEqual(len(self.database.devices.documents), 1)

    def test_reassignment_conflicts_do_not_change_existing_assignment(self):
        device = device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-1"})
        device_service.create_device({"device_id": "ESP32-LAB-02", "vehicle_id": "VEH-2"})

        with self.assertRaisesRegex(RuntimeError, "already has a device"):
            device_service.update_device(device["device_id"], {"vehicle_id": "VEH-2"})

        self.assertEqual(
            self.database.devices.find_one({"device_id": device["device_id"]})["vehicle_id"],
            "VEH-1",
        )

    def test_device_cannot_be_assigned_to_inactive_vehicle(self):
        device = device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-1"})
        self.database.vehicles.update_one(
            {"vehicle_id": "VEH-2"},
            {"$set": {"status": "Inactive"}},
        )

        with self.assertRaisesRegex(ValueError, "not eligible"):
            device_service.update_device(device["device_id"], {"vehicle_id": "VEH-2"})

        self.assertEqual(
            self.database.devices.find_one({"device_id": device["device_id"]})["vehicle_id"],
            "VEH-1",
        )

    def test_transport_rollover_routes_new_readings_and_preserves_old_history(self):
        device = device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-1"})
        old_transport = self.create_transport("CON-A")
        old_reading = {
            "reading_id": "WGT-HISTORY",
            "device_id": device["device_id"],
            "vehicle_id": "VEH-1",
            "transport_id": old_transport["transport_id"],
            "raw_value": -209177,
            "calibration_status": "NOT_SET",
            "weight_kg": None,
            "timestamp": "2026-10-21T00:30:00+00:00",
        }
        self.database.weight_readings.insert_one(old_reading)
        self.complete_verified(old_transport, 1000)

        device = device_service.update_device(device["device_id"], {"vehicle_id": "VEH-2"})
        new_transport = self.create_transport("CON-A", "VEH-2")
        _, _, resolved_transport = device_service.resolve_device_transport(device["device_id"])
        result = weight_service.add_device_weight({
            "device_id": device["device_id"],
            "raw_value": -209100,
            "calibration_status": "NOT_SET",
            "weight_kg": None,
        })

        self.assertEqual(resolved_transport["transport_id"], new_transport["transport_id"])
        self.assertEqual(result["transport_id"], new_transport["transport_id"])
        self.assertEqual(result["vehicle_id"], "VEH-2")
        self.assertEqual(
            self.database.weight_readings.find_one({"reading_id": result["reading"]["reading_id"]})["transport_id"],
            new_transport["transport_id"],
        )
        self.assertEqual(
            self.database.weight_readings.find_one({"reading_id": "WGT-HISTORY"})["transport_id"],
            old_transport["transport_id"],
        )
        self.assertEqual(len(self.database.transport_records.documents), 2)

    def test_closed_transport_is_not_resolved_for_device_telemetry(self):
        device, transport = self.create_mismatched_transport()
        transport_service.close_mismatch_transport(transport["transport_id"], "Reviewed")

        with self.assertRaisesRegex(LookupError, "No active transport"):
            device_service.resolve_device_transport(device["device_id"])

    def test_resolver_rejects_missing_device_vehicle_and_active_transport(self):
        device = device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-1"})
        with self.assertRaisesRegex(LookupError, "No active transport"):
            device_service.resolve_device_transport(device["device_id"])

        self.database.devices.update_one(
            {"device_id": device["device_id"]},
            {"$set": {"vehicle_id": "VEH-MISSING"}},
        )
        with self.assertRaisesRegex(LookupError, "Vehicle not found"):
            device_service.resolve_device_transport(device["device_id"])

        self.database.devices.update_one(
            {"device_id": device["device_id"]},
            {"$set": {"vehicle_id": None}},
        )
        with self.assertRaisesRegex(ValueError, "no vehicle"):
            device_service.resolve_device_transport(device["device_id"])

    def test_resolver_rejects_inconsistent_or_ambiguous_relationships(self):
        device = device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-1"})
        transport = self.create_transport("CON-A")
        self.database.vehicles.update_one(
            {"vehicle_id": "VEH-1"},
            {"$set": {"active_transport_id": "TRN-OTHER"}},
        )
        with self.assertRaisesRegex(ValueError, "assignments are inconsistent"):
            device_service.resolve_device_transport(device["device_id"])

        self.database.vehicles.update_one(
            {"vehicle_id": "VEH-1"},
            {"$set": {"active_transport_id": transport["transport_id"], "current_site_id": "CON-B"}},
        )
        with self.assertRaisesRegex(ValueError, "site assignments are inconsistent"):
            device_service.resolve_device_transport(device["device_id"])

        self.database.vehicles.update_one(
            {"vehicle_id": "VEH-1"},
            {"$set": {"current_site_id": "CON-A"}},
        )
        self.database.construction_sites.update_one(
            {"site_id": "CON-A"},
            {"$set": {"status": "Inactive"}},
        )
        with self.assertRaisesRegex(ValueError, "construction site is not active"):
            device_service.resolve_device_transport(device["device_id"])

        self.database.construction_sites.update_one(
            {"site_id": "CON-A"},
            {"$set": {"status": "Active"}},
        )
        ambiguous = dict(transport)
        ambiguous["transport_id"] = "TRN-AMBIGUOUS"
        self.database.transport_records.insert_one(ambiguous)
        with self.assertRaisesRegex(ValueError, "Multiple active transports"):
            device_service.resolve_device_transport(device["device_id"])

    def test_resolver_rejects_missing_or_unauthorized_facility(self):
        device = device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-1"})
        transport = self.create_transport("CON-A")
        self.database.facilities.update_one(
            {"facility_id": "FAC-1"},
            {"$set": {"authorized": False}},
        )
        with self.assertRaisesRegex(ValueError, "not active and authorized"):
            device_service.resolve_device_transport(device["device_id"])

        self.database.facilities.update_one(
            {"facility_id": "FAC-1"},
            {"$set": {"authorized": True}},
        )
        self.database.transport_records.update_one(
            {"transport_id": transport["transport_id"]},
            {"$set": {"facility_id": "FAC-MISSING"}},
        )
        with self.assertRaisesRegex(LookupError, "facility not found"):
            device_service.resolve_device_transport(device["device_id"])

    def test_resolver_rejects_conflicting_device_assignment_registry(self):
        device = device_service.create_device({"device_id": "ESP32-LAB-01", "vehicle_id": "VEH-1"})
        self.create_transport("CON-A")
        self.database.device_assignments.update_one(
            {"_id": "device:ESP32-LAB-01"},
            {"$set": {"vehicle_id": "VEH-2"}},
        )

        with self.assertRaisesRegex(ValueError, "registry is inconsistent"):
            device_service.resolve_device_transport(device["device_id"])

    def test_concurrent_creates_reserve_only_one_active_transport(self):
        barrier = threading.Barrier(2)
        self.database.transport_records.find_barrier = barrier
        outcomes = []

        def create():
            try:
                outcomes.append(transport_service.create_transport({
                    "site_id": "CON-A",
                    "vehicle_id": "VEH-1",
                    "facility_id": "FAC-1",
                }))
            except Exception as exc:
                outcomes.append(exc)

        threads = [threading.Thread(target=create) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=6)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)
        self.assertEqual(sum(isinstance(item, RuntimeError) for item in outcomes), 1)
        self.assertEqual(len(self.database.transport_records.documents), 1)

    def test_mismatch_closure_preserves_result_history_releases_assignment_and_allows_reuse(self):
        device, transport = self.create_mismatched_transport()
        prior_weights = {
            key: transport[key]
            for key in ("loaded_weight_kg", "received_weight_kg", "weight_difference_kg", "difference_percentage", "weight_status")
        }
        reading_count = len(self.database.weight_readings.documents)
        with self.assertRaisesRegex(ValueError, "Only verified transports"):
            transport_service.complete_transport(transport["transport_id"])

        closed = transport_service.close_mismatch_transport(transport["transport_id"], "Reviewed facility discrepancy")

        self.assertEqual(closed["status"], "Closed")
        self.assertEqual(closed["weight_status"], "Mismatch")
        self.assertEqual(closed["mismatch_closed_from_status"], "Mismatch")
        self.assertEqual({key: closed[key] for key in prior_weights}, prior_weights)
        self.assertEqual(closed["mismatch_closure_reason"], "Reviewed facility discrepancy")
        self.assertEqual(closed["mismatch_reviewed_at"], closed["mismatch_closed_at"])
        vehicle = self.database.vehicles.find_one({"vehicle_id": "VEH-1"})
        self.assertEqual(vehicle["status"], "Available")
        self.assertIsNone(vehicle["current_site_id"])
        self.assertNotIn("active_transport_id", vehicle)
        self.assertEqual(len(self.database.weight_readings.documents), reading_count)
        self.assertIsNotNone(self.database.transport_records.find_one({"transport_id": transport["transport_id"]}))

        new_transport = self.create_transport("CON-A")
        self.assertEqual(new_transport["vehicle_id"], "VEH-1")
        resolved_device, resolved_vehicle, resolved_transport = device_service.resolve_device_transport(
            device["device_id"]
        )
        self.assertEqual(resolved_device["device_id"], device["device_id"])
        self.assertEqual(resolved_vehicle["vehicle_id"], "VEH-1")
        self.assertEqual(resolved_transport["transport_id"], new_transport["transport_id"])
        self.assertEqual(len(self.database.transport_records.documents), 2)

    def test_mismatch_closure_rejects_invalid_requests_and_repeat_closure(self):
        _, transport = self.create_mismatched_transport()
        with self.assertRaisesRegex(ValueError, "reason is required"):
            transport_service.close_mismatch_transport(transport["transport_id"], "  ")
        with self.assertRaisesRegex(ValueError, "500 characters"):
            transport_service.close_mismatch_transport(transport["transport_id"], "x" * 501)

        self.assertEqual(
            transport_service.close_mismatch_transport(transport["transport_id"], "Reviewed").get("status"),
            "Closed",
        )
        with self.assertRaisesRegex(ValueError, "Only transports with a verified mismatch"):
            transport_service.close_mismatch_transport(transport["transport_id"], "Second review")

    def test_mismatch_closure_rejects_non_mismatch_or_invalid_weight_evidence(self):
        transport = self.create_transport("CON-A")
        self.database.transport_records.update_one(
            {"transport_id": transport["transport_id"]},
            {"$set": {"status": "Mismatch", "weight_status": "Mismatch", "loaded_weight_kg": 1000, "received_weight_kg": 990}},
        )
        with self.assertRaisesRegex(ValueError, "do not satisfy"):
            transport_service.close_mismatch_transport(transport["transport_id"], "Review")

        self.database.transport_records.update_one(
            {"transport_id": transport["transport_id"]},
            {"$set": {"received_weight_kg": 800}},
        )
        self.database.vehicles.update_one(
            {"vehicle_id": "VEH-1"},
            {"$set": {"active_transport_id": "TRN-OTHER"}},
        )
        with self.assertRaisesRegex(ValueError, "no longer assigned"):
            transport_service.close_mismatch_transport(transport["transport_id"], "Review")

    def test_concurrent_mismatch_closures_close_and_release_only_once(self):
        _, transport = self.create_mismatched_transport()
        start = threading.Barrier(2)
        outcomes = []

        def close_mismatch():
            start.wait(timeout=5)
            try:
                outcomes.append(transport_service.close_mismatch_transport(transport["transport_id"], "Reviewed"))
            except Exception as exc:
                outcomes.append(exc)

        threads = [threading.Thread(target=close_mismatch) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=6)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(sum(isinstance(item, dict) for item in outcomes), 1)
        self.assertEqual(sum(isinstance(item, ValueError) for item in outcomes), 1)
        closed = self.database.transport_records.find_one({"transport_id": transport["transport_id"]})
        self.assertEqual(closed["status"], "Closed")
        vehicle = self.database.vehicles.find_one({"vehicle_id": "VEH-1"})
        self.assertNotIn("active_transport_id", vehicle)


if __name__ == "__main__":
    unittest.main()