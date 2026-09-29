import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.dashboard_service import _summarize_transports, list_site_summaries, list_site_vehicle_transports


class FakeCursor:
    def __init__(self, documents):
        self.documents = documents

    def sort(self, field, direction):
        self.documents = sorted(self.documents, key=lambda document: document.get(field, ""), reverse=direction < 0)
        return self

    def __iter__(self):
        return iter(self.documents)


class DashboardAggregationTest(unittest.TestCase):
    def test_summary_totals_use_each_transport_once_and_keep_weight_types_separate(self):
        transports = [
            {"status": "Completed", "weight_status": "Verified", "loaded_weight_kg": 1000, "received_weight_kg": 1000},
            {"status": "Completed", "weight_status": "Mismatch", "loaded_weight_kg": 1200, "received_weight_kg": 1100},
            {"status": "In Transit", "weight_status": "Pending", "loaded_weight_kg": None, "received_weight_kg": None},
        ]

        summary = _summarize_transports(transports)

        self.assertEqual(summary["total_transports"], 3)
        self.assertEqual(summary["total_loaded_weight_kg"], 2200)
        self.assertEqual(summary["loaded_weight_records"], 2)
        self.assertEqual(summary["total_received_weight_kg"], 2100)
        self.assertEqual(summary["completed_transports"], 2)
        self.assertEqual(summary["active_transports"], 1)
        self.assertEqual(summary["in_transit_transports"], 1)
        self.assertEqual(summary["verified_transports"], 1)
        self.assertEqual(summary["pending_verification"], 1)
        self.assertEqual(summary["mismatches"], 1)

    def test_site_summaries_group_transport_history_without_double_counting(self):
        sites = Mock()
        sites.find.return_value = [
            {"site_id": "CON-A", "name": "Site A", "status": "Active"},
            {"site_id": "CON-B", "name": "Site B", "status": "Active"},
        ]
        transports = Mock()
        transports.find.return_value = [
            {"site_id": "CON-A", "vehicle_id": "VEH-1", "status": "Completed", "weight_status": "Verified", "loaded_weight_kg": 1000},
            {"site_id": "CON-A", "vehicle_id": "VEH-1", "status": "Completed", "weight_status": "Verified", "loaded_weight_kg": 1200},
            {"site_id": "CON-B", "vehicle_id": "VEH-1", "status": "Completed", "weight_status": "Verified", "loaded_weight_kg": 800},
        ]
        collections = {"construction_sites": sites, "transport_records": transports}

        with patch("services.common.collection", side_effect=collections.__getitem__):
            summaries = list_site_summaries()

        summary_by_site = {summary["site_id"]: summary for summary in summaries}
        self.assertEqual(summary_by_site["CON-A"]["total_transports"], 2)
        self.assertEqual(summary_by_site["CON-A"]["total_vehicles"], 1)
        self.assertEqual(summary_by_site["CON-A"]["total_loaded_weight_kg"], 2200)
        self.assertEqual(summary_by_site["CON-B"]["total_transports"], 1)
        self.assertEqual(summary_by_site["CON-B"]["total_loaded_weight_kg"], 800)

    def test_vehicle_diary_queries_both_site_and_vehicle(self):
        sites = Mock()
        sites.find_one.return_value = {"site_id": "CON-A"}
        vehicles = Mock()
        vehicles.find_one.return_value = {"vehicle_id": "VEH-1"}
        transport_cursor = Mock()
        transport_cursor.sort.return_value = []
        transports = Mock()
        transports.find.return_value = transport_cursor
        collections = {
            "construction_sites": sites,
            "vehicles": vehicles,
            "transport_records": transports,
        }

        with patch("services.common.collection", side_effect=collections.__getitem__):
            result = list_site_vehicle_transports("CON-A", "VEH-1")

        self.assertEqual(result, [])
        transports.find.assert_called_once_with({"site_id": "CON-A", "vehicle_id": "VEH-1"})

    def test_reused_vehicle_diaries_are_isolated_by_site(self):
        site_documents = [{"site_id": "CON-A"}, {"site_id": "CON-B"}]
        transport_documents = [
            {"transport_id": "TRN-A1", "site_id": "CON-A", "vehicle_id": "VEH-1", "created_at": "1"},
            {"transport_id": "TRN-A2", "site_id": "CON-A", "vehicle_id": "VEH-1", "created_at": "2"},
            {"transport_id": "TRN-B1", "site_id": "CON-B", "vehicle_id": "VEH-1", "created_at": "3"},
        ]

        class Collection:
            def __init__(self, documents):
                self.documents = documents
                self.last_query = None

            def find_one(self, query, *args, **kwargs):
                return next((document for document in self.documents if all(document.get(key) == value for key, value in query.items())), None)

            def find(self, query):
                self.last_query = query
                matching = [document for document in self.documents if all(document.get(key) == value for key, value in query.items())]
                return FakeCursor(matching)

        sites = Collection(site_documents)
        vehicles = Collection([{"vehicle_id": "VEH-1"}])
        transports = Collection(transport_documents)
        gps_points = Collection([])
        collections = {
            "construction_sites": sites,
            "vehicles": vehicles,
            "transport_records": transports,
            "gps_tracking": gps_points,
        }

        with patch("services.common.collection", side_effect=collections.__getitem__):
            site_a = list_site_vehicle_transports("CON-A", "VEH-1")
            site_b = list_site_vehicle_transports("CON-B", "VEH-1")

        self.assertEqual({item["transport_id"] for item in site_a}, {"TRN-A1", "TRN-A2"})
        self.assertEqual({item["transport_id"] for item in site_b}, {"TRN-B1"})
        self.assertEqual(transports.last_query, {"site_id": "CON-B", "vehicle_id": "VEH-1"})


if __name__ == "__main__":
    unittest.main()