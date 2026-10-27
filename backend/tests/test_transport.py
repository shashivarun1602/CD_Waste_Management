import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from flask import Flask

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from routes.transport import transport_bp
from services.transport_service import TRANSITIONS, capture_loaded_weight, capture_received_weight, create_transport, get_transport


class TransportLifecycleTest(unittest.TestCase):
    def test_lifecycle_does_not_allow_created_to_completed(self):
        self.assertNotIn('Completed', TRANSITIONS['Created'])

    def test_lifecycle_allows_only_expected_next_states(self):
        self.assertEqual(TRANSITIONS['Loaded'], {'In Transit'})
        self.assertEqual(TRANSITIONS['Verified'], {'Completed'})

    def test_transport_service_accepts_missing_waste_and_driver_ids(self):
        site = Mock()
        site.find_one.return_value = {"site_id": "CON-1", "status": "Active"}
        vehicle = Mock()
        vehicle.find_one.return_value = {"vehicle_id": "VEH-1", "status": "Available", "current_site_id": None}
        vehicle.find_one_and_update.return_value = {"status": "Available", "current_site_id": None}
        facility = Mock()
        facility.find_one.return_value = {"facility_id": "FAC-1", "status": "Active", "authorized": True}
        transports = Mock()
        transports.find_one.return_value = None
        collections = {
            "construction_sites": site,
            "vehicles": vehicle,
            "facilities": facility,
            "transport_records": transports,
        }
        payload = {"site_id": "CON-1", "vehicle_id": "VEH-1", "facility_id": "FAC-1"}

        with patch("services.transport_service.collection", side_effect=collections.__getitem__), patch(
            "services.transport_service.create_document",
            side_effect=lambda name, field, prefix, data, identifier=None: {**data, field: identifier or "TRN-1"},
        ) as create_document, patch("services.transport_service.generate_id", return_value="TRN-1"):
            created = create_transport(payload)

        self.assertEqual(created["transport_id"], "TRN-1")
        self.assertNotIn("waste_id", create_document.call_args.args[3])
        self.assertEqual(create_document.call_args.kwargs["identifier"], "TRN-1")
        self.assertNotIn("driver_id", create_document.call_args.args[3])
        self.assertNotIn("waste_records", collections)
        self.assertNotIn("drivers", collections)

    def test_transport_details_return_only_the_latest_sensor_reading(self):
        transport = {"transport_id": "TRN-1", "vehicle_id": "VEH-1"}
        readings = Mock()
        readings.find_one.return_value = {
            "weight_kg": 2500, "raw_value": 250000, "calibration_status": "SET", "timestamp": "2026-10-01T10:00:00Z"
        }
        devices = Mock()
        devices.find_one.return_value = {"device_id": "ESP-1"}
        collections = {"weight_readings": readings, "devices": devices}

        with patch("services.transport_service.get_document", return_value=transport), patch(
            "services.transport_service.latest_gps_point", return_value=None
        ), patch("services.transport_service.list_documents", return_value=[]) as list_documents, patch(
            "services.transport_service.collection", side_effect=collections.__getitem__
        ):
            result = get_transport("TRN-1")

        self.assertEqual(result["latest_sensor_reading"]["weight_kg"], 2500)
        self.assertNotIn("weight_history", result)
        list_documents.assert_called_once_with("gps_tracking", {"transport_id": "TRN-1"}, "timestamp")
        self.assertEqual(readings.find_one.call_args.kwargs["sort"], [("timestamp", -1)])

    def test_transport_api_accepts_only_current_required_ids(self):
        payload = {"site_id": "CON-1", "vehicle_id": "VEH-1", "facility_id": "FAC-1"}
        app = Flask(__name__)
        app.register_blueprint(transport_bp, url_prefix="/api")
        with patch("routes.transport.transport_service.create_transport", return_value={"transport_id": "TRN-1"}) as create:
            response = app.test_client().post("/api/transports", json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(create.call_args.args[0], payload)

    def test_capture_load_uses_latest_calibrated_sensor_reading(self):
        transport_collection = Mock()
        transport_collection.find_one.return_value = {"transport_id": "TRN-1", "status": "Created", "loaded_weight_kg": None}
        readings_collection = Mock()
        readings_collection.find_one.return_value = {"weight_kg": 2500, "device_id": "ESP-1", "calibration_status": "SET"}
        collections = {"transport_records": transport_collection, "weight_readings": readings_collection}

        with patch("services.transport_service.collection", side_effect=collections.__getitem__), patch(
            "services.transport_service.load_transport", return_value={"loaded_weight_kg": 2500}
        ) as load:
            result = capture_loaded_weight("TRN-1")

        self.assertEqual(result["loaded_weight_kg"], 2500)
        self.assertEqual(load.call_args.args, ("TRN-1", 2500, "device", "ESP-1"))
        self.assertEqual(readings_collection.find_one.call_args.args[0], {
            "transport_id": "TRN-1", "weight_kg": {"$gt": 0}, "calibration_status": "SET"
        })

    def test_capture_received_weight_does_not_overwrite_an_existing_capture(self):
        transport_collection = Mock()
        transport_collection.find_one.return_value = {
            "transport_id": "TRN-1", "status": "Arrived", "received_weight_kg": 2475
        }
        with patch("services.transport_service.collection", return_value=transport_collection), patch(
            "services.transport_service._latest_calibrated_reading"
        ) as latest_reading:
            with self.assertRaisesRegex(ValueError, "already been captured"):
                capture_received_weight("TRN-1")
        latest_reading.assert_not_called()

    def test_capture_received_weight_arrives_with_latest_sensor_reading(self):
        transport_collection = Mock()
        transport_collection.find_one.return_value = {
            "transport_id": "TRN-1", "status": "In Transit", "received_weight_kg": None
        }
        with patch("services.transport_service.collection", return_value=transport_collection), patch(
            "services.transport_service._latest_calibrated_reading",
            return_value={"weight_kg": 2475, "device_id": "ESP-1"},
        ), patch("services.transport_service.arrive_transport", return_value={"status": "Arrived"}) as arrive:
            result = capture_received_weight("TRN-1")

        self.assertEqual(result["status"], "Arrived")
        arrive.assert_called_once_with("TRN-1", 2475, "device", "ESP-1")

    def test_capture_weight_routes_are_explicit_actions(self):
        app = Flask(__name__)
        app.register_blueprint(transport_bp, url_prefix="/api")
        client = app.test_client()
        with patch(
            "routes.transport.transport_service.capture_loaded_weight",
            return_value={"loaded_weight_kg": 2500},
        ) as capture_load, patch(
            "routes.transport.transport_service.capture_received_weight",
            return_value={"received_weight_kg": 2475},
        ) as capture_received:
            loaded = client.post("/api/transports/TRN-1/capture-load", json={})
            received = client.post("/api/transports/TRN-1/capture-received", json={})

        self.assertEqual(loaded.status_code, 200)
        self.assertEqual(loaded.get_json()["data"]["loaded_weight_kg"], 2500)
        self.assertEqual(received.status_code, 200)
        self.assertEqual(received.get_json()["data"]["received_weight_kg"], 2475)
        capture_load.assert_called_once_with("TRN-1")
        capture_received.assert_called_once_with("TRN-1")

    def test_mismatch_closure_route_requires_service_validation_and_returns_closed_transport(self):
        app = Flask(__name__)
        app.register_blueprint(transport_bp, url_prefix="/api")
        client = app.test_client()
        with patch(
            "routes.transport.transport_service.close_mismatch_transport",
            return_value={
                "transport_id": "TRN-1",
                "status": "Closed",
                "weight_status": "Mismatch",
                "mismatch_closure_reason": "Reviewed",
            },
        ) as close_mismatch:
            response = client.post("/api/transports/TRN-1/close-mismatch", json={"reason": " Reviewed "})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["status"], "Closed")
        self.assertEqual(response.get_json()["data"]["weight_status"], "Mismatch")
        close_mismatch.assert_called_once_with("TRN-1", " Reviewed ")

    def test_mismatch_closure_route_reports_invalid_closure(self):
        app = Flask(__name__)
        app.register_blueprint(transport_bp, url_prefix="/api")
        with patch(
            "routes.transport.transport_service.close_mismatch_transport",
            side_effect=ValueError("A mismatch review reason is required"),
        ):
            response = app.test_client().post("/api/transports/TRN-1/close-mismatch", json={})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "MISMATCH_CLOSURE_FAILED")


if __name__ == '__main__':
    unittest.main()
