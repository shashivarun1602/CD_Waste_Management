from services.common import collection, create_document, list_documents, now


def add_gps_point(data):
    data = dict(data)
    data.setdefault("source", "manual")
    data.setdefault("timestamp", now())
    return create_document("gps_tracking", "tracking_id", "GPS", data)


def list_gps_points(transport_id=None):
    query = {"transport_id": transport_id} if transport_id else {}
    return list_documents("gps_tracking", query, "timestamp")


def latest_gps_point(transport_id):
    document = collection("gps_tracking").find_one({"transport_id": transport_id}, sort=[("timestamp", -1)])
    from utils.response import document_to_dict
    return document_to_dict(document)
