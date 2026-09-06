from flask import jsonify


def success(data=None, message="Success", status=200):
    return jsonify({"success": True, "message": message, "data": data}), status


def error(message, code, status=400):
    return jsonify({"success": False, "message": message, "error": code}), status


def document_to_dict(document):
    if not document:
        return None
    result = dict(document)
    result.pop("_id", None)
    return result
