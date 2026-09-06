from config import Config


def verify_weights(loaded_weight_kg, received_weight_kg):
    difference = round(loaded_weight_kg - received_weight_kg, 3)
    percentage = round(abs(difference) / loaded_weight_kg * 100, 3) if loaded_weight_kg else 0
    status = "Verified" if percentage <= Config.VERIFICATION_THRESHOLD_PERCENT else "Mismatch"
    return {
        "weight_difference_kg": difference,
        "difference_percentage": percentage,
        "weight_status": status,
    }
