ALLOWED_SOURCES = {"manual", "device", "api"}
WASTE_TYPES = {"Concrete", "Bricks", "Soil", "Metal", "Wood", "Glass", "Asphalt", "Mixed C&D", "Other"}


def missing_fields(data, fields):
    return [field for field in fields if data.get(field) in (None, "")]


def validate_source(data):
    source = data.get("source", "manual")
    if source not in ALLOWED_SOURCES:
        return f"source must be one of: {', '.join(sorted(ALLOWED_SOURCES))}"
    if source == "device" and not data.get("device_id"):
        return "device_id is required when source is device"
    return None


def positive_number(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None, f"{field} must be a number"
    if number < 0:
        return None, f"{field} cannot be negative"
    return number, None
