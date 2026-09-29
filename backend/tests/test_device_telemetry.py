import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from services.device_service import _online_status, resolve_device_transport
from services.weight_service import add_device_weight


class DeviceTelemetryRouteTest(unittest.TestCase):
    def setUp(self):
        app.config["DEVICE_API_TOKEN"] = "test-device-token"
        self.api = app.test_client()
        self.headers = {"X-Device-Token": "test-device-token"}

    def test_missing_or_wrong_token_is_rejected(self):
        response = self.api.post("/api/device/gps", json={"device_id": "DEV-0001"})
        self.assertEqual(response.status_code, 401)

        response = self.api.post(
            "/api/device/gps",
            json={"device_id": "DEV-0001"},
            headers={"X-Device-Token": "wrong-token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_unconfigured_device_token_fails_closed(self):
        app.config["DEVICE_API_TOKEN"] = ""
        response = self.api.post("/api/device/gps", json={"device_id": "DEV-0001"})
        self.assertEqual(response.status_code, 503)

    @patch("routes.device_data.gps_service.add_device_gps_point")
    def test_gps_route_forwards_device_transport_and_fix_metadata(self, add_point):
        add_point.return_value = {"tracking_id": "GPS-0001"}
        payload = {
            "device_id": "DEV-0001",
            "transport_id": "TRN-0001",
            "latitude": 17.385,
            "longitude": 78.4867,
            "satellites": 8,
            "gps_fix": True,
            "timestamp": "2026-09-29T10:00:00Z",
        }

        response = self.api.post("/api/device/gps", json=payload, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        forwarded = add_point.call_args.args[0]
        self.assertEqual(forwarded["transport_id"], "TRN-0001")
        self.assertEqual(forwarded["satellites"], 8)
        self.assertEqual(forwarded["source"], "device")

    @patch("routes.device_data.weight_service.add_device_weight")
    def test_raw_weight_is_not_converted_to_kilograms(self, add_weight):
        add_weight.return_value = {"weight_kg": None, "raw_value": -209177}
        payload = {
            "device_id": "DEV-0001",
            "transport_id": "TRN-0001",
            "raw_value": -209177,
            "calibration_status": "NOT_SET",
            "weight_kg": None,
            "timestamp": "2026-09-29T10:00:00Z",
        }

        response = self.api.post("/api/device/weight", json=payload, headers=self.headers)

        self.assertEqual(response.status_code, 200)
        forwarded = add_weight.call_args.args[0]
        self.assertEqual(forwarded["raw_value"], -209177)
        self.assertEqual(forwarded["calibration_status"], "NOT_SET")
        self.assertIsNone(forwarded["weight_kg"])

    @patch("routes.device_data.weight_service.add_device_weight")
    def test_existing_calibrated_weight_payload_is_preserved(self, add_weight):
        add_weight.return_value = {"weight_kg": 8420}
        response = self.api.post(
            "/api/device/weight",
            json={"device_id": "DEV-0001", "weight_kg": 8420},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(add_weight.call_args.args[0]["weight_kg"], 8420.0)

    def test_raw_value_cannot_be_marked_calibrated_without_kilograms(self):
        response = self.api.post(
            "/api/device/weight",
            json={"device_id": "DEV-0001", "raw_value": -209177, "calibration_status": "SET"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_resolver_rejects_unknown_device_without_database(self):
        with patch("services.device_service.collection") as collection:
            collection.return_value.find_one.return_value = None
            with self.assertRaises(LookupError):
                resolve_device_transport("DEV-MISSING", "TRN-0001")

    def test_resolver_rejects_inactive_device_without_database(self):
        devices = Mock()
        devices.find_one.return_value = {"device_id": "DEV-0001", "status": "inactive"}
        with patch("services.device_service.collection", return_value=devices):
            with self.assertRaises(ValueError):
                resolve_device_transport("DEV-0001", "TRN-0001")

    def test_resolver_rejects_transport_assigned_to_another_vehicle(self):
        devices = Mock()
        devices.find_one.return_value = {"device_id": "DEV-0001", "vehicle_id": "VEH-0001", "status": "active"}
        vehicles = Mock()
        vehicles.find_one.return_value = {"vehicle_id": "VEH-0001"}
        transports = Mock()
        transports.find_one.side_effect = [None, {"transport_id": "TRN-0002", "vehicle_id": "VEH-0002"}]
        collections = {"devices": devices, "vehicles": vehicles, "transport_records": transports}
        with patch("services.device_service.collection", side_effect=collections.__getitem__):
            with self.assertRaises(ValueError):
                resolve_device_transport("DEV-0001", "TRN-0002")

    def test_online_status_uses_recent_server_heartbeat(self):
        recent = datetime.now(timezone.utc).isoformat()
        self.assertEqual(_online_status("active", recent), "ONLINE")
        self.assertEqual(_online_status("inactive", recent), "OFFLINE")
        self.assertEqual(_online_status("active", None), "OFFLINE")

    @patch("services.weight_service.touch_device")
    @patch("services.weight_service.collection")
    @patch("services.weight_service.create_document", return_value={"reading_id": "WGT-0001"})
    @patch("services.weight_service.resolve_device_transport")
    def test_raw_weight_persistence_does_not_mutate_transport_kilograms(self, resolve, create, collection, touch):
        resolve.return_value = (
            {"device_id": "DEV-0001"},
            {"vehicle_id": "VEH-0001"},
            {"transport_id": "TRN-0001", "status": "Created"},
        )
        transport_collection = Mock()
        collection.return_value = transport_collection

        result = add_device_weight({
            "device_id": "DEV-0001",
            "transport_id": "TRN-0001",
            "raw_value": -209177,
            "calibration_status": "NOT_SET",
            "weight_kg": None,
        })

        stored_reading = create.call_args.args[3]
        self.assertEqual(stored_reading["raw_value"], -209177)
        self.assertEqual(stored_reading["calibration_status"], "NOT_SET")
        self.assertIsNone(stored_reading["weight_kg"])
        updates = transport_collection.update_one.call_args.args[1]["$set"]
        self.assertNotIn("loaded_weight_kg", updates)
        self.assertNotIn("status", updates)
        self.assertIsNone(result["weight_kg"])
        touch.assert_called_once()


if __name__ == "__main__":
    unittest.main()