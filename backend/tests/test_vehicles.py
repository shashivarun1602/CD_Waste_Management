import unittest


class VehicleHistoryTest(unittest.TestCase):
    def test_vehicle_identity_is_separate_from_transport_identity(self):
        vehicle_id = 'VEH-0001'
        trips = [{'transport_id': 'TRN-0001', 'vehicle_id': vehicle_id, 'site_id': 'CON-0001'}, {'transport_id': 'TRN-0007', 'vehicle_id': vehicle_id, 'site_id': 'CON-0003'}]
        self.assertEqual({trip['vehicle_id'] for trip in trips}, {vehicle_id})
        self.assertEqual(len(trips), 2)


if __name__ == '__main__':
    unittest.main()
