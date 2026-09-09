from db import get_database
from services.common import now


def seed():
    database = get_database()
    timestamp = now()
    database.construction_sites.delete_many({"demo": True})
    database.vehicles.delete_many({"demo": True})
    database.drivers.delete_many({"demo": True})
    database.facilities.delete_many({"demo": True})
    database.waste_records.delete_many({"demo": True})
    database.devices.delete_many({"demo": True})
    database.transport_records.delete_many({"demo": True})
    database.gps_tracking.delete_many({"demo": True})
    database.weight_readings.delete_many({"demo": True})
    database.construction_sites.insert_many([
        {"site_id": "CON-DEMO-01", "name": "Riverstone Build", "project_name": "Riverstone Homes", "site_type": "Construction", "address": "Hyderabad", "latitude": 17.385, "longitude": 78.4867, "status": "Active", "demo": True, "created_at": timestamp, "updated_at": timestamp},
        {"site_id": "CON-DEMO-02", "name": "North Loop Demolition", "project_name": "North Loop Renewal", "site_type": "Demolition", "address": "Secunderabad", "latitude": 17.4399, "longitude": 78.4983, "status": "Active", "demo": True, "created_at": timestamp, "updated_at": timestamp},
    ])
    database.vehicles.insert_many([{ "vehicle_id": f"VEH-DEMO-0{index}", "registration_number": f"TS09DEMO0{index}", "vehicle_type": "Tipper Truck", "capacity_kg": 10000, "status": "Available", "demo": True, "created_at": timestamp, "updated_at": timestamp } for index in range(1, 4)])
    database.drivers.insert_many([{ "driver_id": f"DRV-DEMO-0{index}", "name": f"Demo Driver {index}", "license_number": f"DEMO-LIC-0{index}", "status": "Available", "demo": True, "created_at": timestamp, "updated_at": timestamp } for index in range(1, 4)])
    database.facilities.insert_many([
        {"facility_id": "FAC-DEMO-01", "name": "Greenline Recycling", "facility_type": "Recycling", "address": "Hyderabad", "latitude": 17.4000, "longitude": 78.5000, "authorized": True, "authorized_waste_types": ["concrete", "bricks", "mixed_cnd"], "status": "Active", "demo": True, "created_at": timestamp, "updated_at": timestamp},
        {"facility_id": "FAC-DEMO-02", "name": "Circular Materials Hub", "facility_type": "Processing", "address": "Secunderabad", "latitude": 17.4500, "longitude": 78.5200, "authorized": True, "authorized_waste_types": ["metal", "wood"], "status": "Active", "demo": True, "created_at": timestamp, "updated_at": timestamp},
    ])
    database.devices.insert_many([
        {"device_id": "ESP-DEMO-01", "vehicle_id": "VEH-DEMO-01", "status": "active", "device_type": "ESP32", "demo": True, "created_at": timestamp, "updated_at": timestamp, "last_seen": None},
        {"device_id": "ESP-DEMO-02", "vehicle_id": "VEH-DEMO-02", "status": "active", "device_type": "ESP32", "demo": True, "created_at": timestamp, "updated_at": timestamp, "last_seen": None},
        {"device_id": "ESP-DEMO-03", "vehicle_id": "VEH-DEMO-03", "status": "inactive", "device_type": "ESP32", "demo": True, "created_at": timestamp, "updated_at": timestamp, "last_seen": None},
    ])
    database.transport_records.insert_one({
        "transport_id": "TRN-DEMO-01", "site_id": "CON-DEMO-01", "vehicle_id": "VEH-DEMO-01", "driver_id": "DRV-DEMO-01", "facility_id": "FAC-DEMO-01", "waste_id": "WST-DEMO-01", "status": "In Transit", "source": "manual", "loaded_weight_kg": 2250, "received_weight_kg": None, "weight_status": "Pending", "created_at": timestamp, "updated_at": timestamp,
    })
    database.vehicles.update_one({"vehicle_id": "VEH-DEMO-01"}, {"$set": {"status": "In Transit", "current_site_id": "CON-DEMO-01", "updated_at": timestamp}})
    database.drivers.update_one({"driver_id": "DRV-DEMO-01"}, {"$set": {"status": "On Trip", "updated_at": timestamp}})
    database.waste_records.insert_many([{ "waste_id": f"WST-DEMO-0{index}", "site_id": "CON-DEMO-01", "waste_type": waste_type, "estimated_weight_kg": 2000 + index * 250, "weight_source": "manual", "demo": True, "created_at": timestamp, "updated_at": timestamp } for index, waste_type in enumerate(["Concrete", "Bricks", "Metal"], 1)])
    print("Demo data inserted into cd_waste_management")


if __name__ == "__main__":
    seed()
