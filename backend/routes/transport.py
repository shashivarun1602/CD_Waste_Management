from flask import Blueprint, request

from services import transport_service
from utils.response import error, success
from utils.validators import missing_fields, positive_number, validate_source

transport_bp = Blueprint("transport", __name__)


@transport_bp.get("/transports")
def list_transports():
    status = request.args.get("status")
    query = {"status": status} if status else None
    return success(transport_service.list_transports(query), "Transports loaded")


@transport_bp.get("/transports/<transport_id>")
def get_transport(transport_id):
    transport = transport_service.get_transport(transport_id)
    return success(transport, "Transport loaded") if transport else error("Transport not found", "TRANSPORT_NOT_FOUND", 404)


@transport_bp.post("/transports")
def create_transport():
    data = request.get_json(silent=True) or {}
    missing = missing_fields(data, ["site_id", "vehicle_id", "driver_id", "facility_id", "waste_id"])
    if missing:
        return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
    try:
        return success(transport_service.create_transport(data), "Transport created successfully", 201)
    except LookupError as exc:
        return error(str(exc), "REFERENCE_NOT_FOUND", 404)
    except RuntimeError as exc:
        return error(str(exc), "RESOURCE_BUSY", 409)
    except ValueError as exc:
        return error(str(exc), "INVALID_TRANSPORT")


def _weight_payload():
    data = request.get_json(silent=True) or {}
    value, message = positive_number(data.get("weight_kg"), "weight_kg")
    if message:
        return None, error(message, "INVALID_WEIGHT")
    source_error = validate_source(data)
    if source_error:
        return None, error(source_error, "INVALID_SOURCE")
    data["weight_kg"] = value
    return data, None


@transport_bp.post("/transports/<transport_id>/load")
def load_transport(transport_id):
    data, response = _weight_payload()
    if response:
        return response
    try:
        return success(transport_service.load_transport(transport_id, data["weight_kg"], data.get("source", "manual"), data.get("device_id")), "Transport loaded")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "INVALID_LIFECYCLE", 404 if isinstance(exc, LookupError) else 400)


@transport_bp.post("/transports/<transport_id>/start")
def start_transport(transport_id):
    try:
        return success(transport_service.start_transport(transport_id), "Transport started")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "INVALID_LIFECYCLE", 404 if isinstance(exc, LookupError) else 400)


@transport_bp.post("/transports/<transport_id>/arrive")
def arrive_transport(transport_id):
    data = request.get_json(silent=True) or {}
    received_weight = data.get("received_weight_kg")
    if received_weight is not None:
        received_weight, message = positive_number(received_weight, "received_weight_kg")
        if message:
            return error(message, "INVALID_WEIGHT")
    source_error = validate_source(data)
    if source_error:
        return error(source_error, "INVALID_SOURCE")
    try:
        return success(transport_service.arrive_transport(transport_id, received_weight, data.get("source", "manual"), data.get("device_id")), "Transport arrived")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "INVALID_LIFECYCLE", 404 if isinstance(exc, LookupError) else 400)


@transport_bp.post("/transports/<transport_id>/verify")
def verify_transport(transport_id):
    try:
        return success(transport_service.verify_transport(transport_id), "Transport weight verified")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "VERIFICATION_FAILED", 404 if isinstance(exc, LookupError) else 400)


@transport_bp.post("/transports/<transport_id>/complete")
def complete_transport(transport_id):
    try:
        return success(transport_service.complete_transport(transport_id), "Transport completed")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "COMPLETION_FAILED", 404 if isinstance(exc, LookupError) else 400)


@transport_bp.post("/transports/<transport_id>/weight")
def record_weight(transport_id):
    data, response = _weight_payload()
    if response:
        return response
    try:
        return success(transport_service.record_weight(transport_id, data), "Weight recorded")
    except (LookupError, ValueError) as exc:
        return error(str(exc), "WEIGHT_RECORDING_FAILED", 404 if isinstance(exc, LookupError) else 400)
