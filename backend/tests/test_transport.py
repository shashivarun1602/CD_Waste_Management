import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app
from services.transport_service import TRANSITIONS, create_transport


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
        vehicle.find_one.return_value = {"vehicle_id": "VEH-1"}
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
            side_effect=lambda name, field, prefix, data: {**data, field: "TRN-1"},
        ) as create_document:
            created = create_transport(payload)

        self.assertEqual(created["transport_id"], "TRN-1")
        self.assertNotIn("waste_id", create_document.call_args.args[3])
        self.assertNotIn("driver_id", create_document.call_args.args[3])
        self.assertNotIn("waste_records", collections)
        self.assertNotIn("drivers", collections)

    def test_transport_api_accepts_only_current_required_ids(self):
        payload = {"site_id": "CON-1", "vehicle_id": "VEH-1", "facility_id": "FAC-1"}
        with patch("routes.transport.transport_service.create_transport", return_value={"transport_id": "TRN-1"}) as create:
            response = app.test_client().post("/api/transports", json=payload)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(create.call_args.args[0], payload)


if __name__ == '__main__':
    unittest.main()
