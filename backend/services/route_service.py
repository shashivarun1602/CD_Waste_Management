from math import asin, cos, radians, sin, sqrt

from config import Config
from services.common import collection, now


def haversine_meters(latitude_a, longitude_a, latitude_b, longitude_b):
    radius = 6371000
    delta_latitude = radians(latitude_b - latitude_a)
    delta_longitude = radians(longitude_b - longitude_a)
    value = sin(delta_latitude / 2) ** 2 + cos(radians(latitude_a)) * cos(radians(latitude_b)) * sin(delta_longitude / 2) ** 2
    return 2 * radius * asin(sqrt(value))


def _point_xy(latitude, longitude, origin_latitude):
    scale = 111320
    return longitude * scale * cos(radians(origin_latitude)), latitude * scale


def _distance_to_segment(point, start, end):
    origin_latitude = start[0]
    point_x, point_y = _point_xy(point[0], point[1], origin_latitude)
    start_x, start_y = _point_xy(start[0], start[1], origin_latitude)
    end_x, end_y = _point_xy(end[0], end[1], origin_latitude)
    delta_x, delta_y = end_x - start_x, end_y - start_y
    length_squared = delta_x * delta_x + delta_y * delta_y
    if not length_squared:
        return sqrt((point_x - start_x) ** 2 + (point_y - start_y) ** 2)
    projection = ((point_x - start_x) * delta_x + (point_y - start_y) * delta_y) / length_squared
    projection = max(0, min(1, projection))
    closest_x = start_x + projection * delta_x
    closest_y = start_y + projection * delta_y
    return sqrt((point_x - closest_x) ** 2 + (point_y - closest_y) ** 2)


def evaluate_route(transport, latitude, longitude):
    facility = collection("facilities").find_one({"facility_id": transport.get("facility_id")})
    if not facility or facility.get("latitude") is None or facility.get("longitude") is None:
        return "NO_ROUTE", None
    destination = (float(facility["latitude"]), float(facility["longitude"]))
    origin = transport.get("route_origin")
    if origin:
        origin = (float(origin["latitude"]), float(origin["longitude"]))
    else:
        origin = (latitude, longitude)
    deviation = _distance_to_segment((latitude, longitude), origin, destination)
    status = "ON_ROUTE" if deviation <= Config.ROUTE_DEVIATION_THRESHOLD_METERS else "DEVIATION"
    return status, round(deviation, 2)


def set_route_origin(transport_id, latitude, longitude):
    collection("transport_records").update_one(
        {"transport_id": transport_id, "route_origin": {"$exists": False}},
        {"$set": {"route_origin": {"latitude": latitude, "longitude": longitude}, "updated_at": now()}},
    )