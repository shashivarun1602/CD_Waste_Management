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
    database.construction_sites.insert_many([
        {"site_id": "CON-DEMO-01", "name": "Riverstone Build", "project_name": "Riverstone Homes", "site_type": "Construction", "address": "Hyderabad", "status": "Active", "demo": True, "created_at": timestamp, "updated_at": timestamp},
        {"site_id": "CON-DEMO-02", "name": "North Loop Demolition", "project_name": "North Loop Renewal", "site_type": "Demolition", "address": "Secunderabad", "status": "Active", "demo": True, "created_at": timestamp, "updated_at": timestamp},
    ])
    database.vehicles.insert_many([{ "vehicle_id": f"VEH-DEMO-0{index}", "registration_number": f"TS09DEMO0{index}", "vehicle_type": "Tipper Truck", "capacity_kg": 10000, "status": "Available", "demo": True, "created_at": timestamp, "updated_at": timestamp } for index in range(1, 4)])
    database.drivers.insert_many([{ "driver_id": f"DRV-DEMO-0{index}", "name": f"Demo Driver {index}", "license_number": f"DEMO-LIC-0{index}", "status": "Available", "demo": True, "created_at": timestamp, "updated_at": timestamp } for index in range(1, 4)])
    database.facilities.insert_many([
        {"facility_id": "FAC-DEMO-01", "name": "Greenline Recycling", "facility_type": "Recycling", "address": "Hyderabad", "authorized": True, "status": "Active", "demo": True, "created_at": timestamp, "updated_at": timestamp},
        {"facility_id": "FAC-DEMO-02", "name": "Circular Materials Hub", "facility_type": "Processing", "address": "Secunderabad", "authorized": True, "status": "Active", "demo": True, "created_at": timestamp, "updated_at": timestamp},
    ])
    database.waste_records.insert_many([{ "waste_id": f"WST-DEMO-0{index}", "site_id": "CON-DEMO-01", "waste_type": waste_type, "estimated_weight_kg": 2000 + index * 250, "weight_source": "manual", "demo": True, "created_at": timestamp, "updated_at": timestamp } for index, waste_type in enumerate(["Concrete", "Bricks", "Metal"], 1)])
    print("Demo data inserted into cd_waste_management")


if __name__ == "__main__":
    seed()
