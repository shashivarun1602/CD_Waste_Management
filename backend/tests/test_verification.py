import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.verification_service import verify_weights


class VerificationTest(unittest.TestCase):
    def test_weight_within_threshold_is_verified(self):
        result = verify_weights(2500, 2475)
        self.assertEqual(result['weight_status'], 'Verified')
        self.assertEqual(result['weight_difference_kg'], 25)

    def test_weight_outside_threshold_is_mismatch(self):
        result = verify_weights(2500, 2300)
        self.assertEqual(result['weight_status'], 'Mismatch')


if __name__ == '__main__':
    unittest.main()
