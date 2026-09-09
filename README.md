# C&D Waste Management & Verification System

A software-only Flask and MongoDB MVP for tracking construction and demolition waste from a construction site through loading, transport, GPS tracking, authorized facility receipt, weight verification, and completion.

## Architecture

- `backend/routes/`: REST endpoints and request validation
- `backend/services/`: CRUD, transport lifecycle, verification, and GPS business logic
- `backend/utils/`: IDs, validation, and common response envelopes
- `frontend/`: HTML/CSS/JavaScript operations dashboard
- MongoDB database: `cd_waste_management`
- Hardware simulation: the dashboard sends simulated ESP32 data through `/api/device/gps` and `/api/device/weight`.

Manual data remains supported. Device GPS and weight requests resolve `Device -> Vehicle -> Active Transport` on the server, so the client cannot assign readings to an arbitrary transport. No physical ESP32, HX711, GPS, or load-cell hardware is required for the demonstration.

## Setup

Start MongoDB locally at `mongodb://localhost:27017`, then run:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r backend\requirements.txt
python backend\app.py
```

Open `http://localhost:5000`. Configuration is in `backend/.env`; credentials are excluded from Git.

Optional demo data:

```powershell
python backend\seed.py
```

## Collections

`construction_sites`, `vehicles`, `drivers`, `facilities`, `waste_records`, `transport_records`, `gps_tracking`, `devices`, and `weight_readings` are created/indexed by the backend. The internal `counters` collection generates permanent IDs. GPS and weight histories remain separate records associated with their resolved transport.

## API

All responses use `{ "success": true, "message": "...", "data": ... }` or the matching error envelope.

- `GET|POST /api/sites`, `GET|PUT|DELETE /api/sites/<site_id>`
- `GET|POST /api/vehicles`, `GET|PUT|DELETE /api/vehicles/<vehicle_id>`, `GET /api/vehicles/<vehicle_id>/history`
- `GET|POST /api/drivers`, `GET|PUT|DELETE /api/drivers/<driver_id>`
- `GET|POST /api/facilities`, `GET|PUT|DELETE /api/facilities/<facility_id>`
- `GET|POST /api/waste`, `GET|PUT|DELETE /api/waste/<waste_id>`
- `GET|POST /api/transports`, `GET /api/transports/<transport_id>`
- `POST /api/transports/<transport_id>/load|start|arrive|verify|complete|weight`
- `GET|POST /api/gps`, `GET /api/gps?transport_id=TRN-0001`
- `GET|POST /api/devices`, `GET|PUT|DELETE /api/devices/<device_id>`
- `POST /api/device/gps`, `POST /api/device/weight`, `GET /api/device/weight?transport_id=TRN-0001`
- `GET /api/facilities/recommend?waste_type=Concrete&latitude=17.385&longitude=78.4867`
- `GET /api/dashboard`, `GET /health`

Transport status is enforced as `Created -> Loaded -> In Transit -> Arrived -> Verified -> Completed`. A weight mismatch is marked `Mismatch` and cannot be completed automatically.

## Testing

```powershell
.venv\Scripts\python.exe -m unittest discover -s backend\tests -p "test_*.py"
```

The tests cover common responses, weight verification, lifecycle restrictions, vehicle reuse semantics, device routing, invalid/inactive device rejection, weight history, facility filtering, and GPS route compliance. Full MongoDB integration testing requires a running MongoDB instance.
