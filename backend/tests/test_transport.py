import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.transport_service import TRANSITIONS


class TransportLifecycleTest(unittest.TestCase):
    def test_lifecycle_does_not_allow_created_to_completed(self):
        self.assertNotIn('Completed', TRANSITIONS['Created'])

    def test_lifecycle_allows_only_expected_next_states(self):
        self.assertEqual(TRANSITIONS['Loaded'], {'In Transit'})
        self.assertEqual(TRANSITIONS['Verified'], {'Completed'})


if __name__ == '__main__':
    unittest.main()
