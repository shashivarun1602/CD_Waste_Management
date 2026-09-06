from flask import request
from pymongo.errors import DuplicateKeyError

from utils.response import error, success
from utils.validators import missing_fields


def register_crud(blueprint, path, service, required_fields, name):
    identifier = service.FIELD

    @blueprint.get(f"/{path}")
    def list_items():
        return success(service.list_items(), f"{name} list loaded")

    @blueprint.get(f"/{path}/<item_id>")
    def get_item(item_id):
        item = service.get_item(item_id)
        return success(item, f"{name} loaded") if item else error(f"{name} not found", "NOT_FOUND", 404)

    @blueprint.post(f"/{path}")
    def create_item():
        data = request.get_json(silent=True) or {}
        missing = missing_fields(data, required_fields)
        if missing:
            return error(f"Missing required fields: {', '.join(missing)}", "MISSING_FIELDS")
        try:
            return success(service.create_item(data), f"{name} created successfully", 201)
        except DuplicateKeyError:
            return error(f"Duplicate {name.lower()} value", "DUPLICATE", 409)
        except ValueError as exc:
            return error(str(exc), "INVALID_DATA")

    @blueprint.put(f"/{path}/<item_id>")
    def update_item(item_id):
        if not service.get_item(item_id):
            return error(f"{name} not found", "NOT_FOUND", 404)
        try:
            return success(service.update_item(item_id, request.get_json(silent=True) or {}), f"{name} updated successfully")
        except DuplicateKeyError:
            return error(f"Duplicate {name.lower()} value", "DUPLICATE", 409)

    @blueprint.delete(f"/{path}/<item_id>")
    def delete_item(item_id):
        if not service.get_item(item_id):
            return error(f"{name} not found", "NOT_FOUND", 404)
        return success(service.delete_item(item_id), f"{name} deactivated successfully")
