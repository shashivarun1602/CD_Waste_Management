# C&D Waste Management & Verification System

A software-only Flask and MongoDB MVP for tracking construction and demolition waste from a construction site through loading, transport, GPS tracking, authorized facility receipt, weight verification, and completion.

## Architecture

- `backend/routes/`: REST endpoints and request validation
- `backend/services/`: CRUD, transport lifecycle, verification, and GPS business logic
- `backend/utils/`: IDs, validation, and common response envelopes
- `frontend/`: HTML/CSS/JavaScript operations dashboard
- MongoDB database: `cd_waste_management`
- Hardware simulation: the dashboard sends simulated ESP32 data through `/api/device/gps` and `/api/device/weight`.

Manual data remains supported. Device GPS and weight requests resolve `Device -> assigned Vehicle -> unique active Transport -> active Construction Site and authorized Facility` on the server, so clients cannot route readings to arbitrary records. A device remains configured with its permanent device ID across transport changes and vehicle reassignment. No physical ESP32, HX711, GPS, or load-cell hardware is required for the demonstration.

Every device weight upload is retained as a sensor-history reading for diagnostics, but uploads do not set or replace the transport's official loaded or received weight. Use the transport detail page's explicit **Capture site-loading weight** and **Capture facility-received weight** actions to record the latest calibrated sensor reading as an official weight. The detail page shows those official weights, verification results, and the latest sensor reading without displaying the full sensor history.

Transports with a verified weight mismatch remain active until an operator explicitly closes them from the transport detail page with a review reason. Closure preserves the original weights and `Mismatch` verification result, records the review/closure timestamps, and releases the vehicle only if it is still assigned to that transport. A closed mismatch is retained in transport history and is not marked `Verified` or `Completed`.

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

`construction_sites`, `vehicles`, `drivers`, `facilities`, `waste_records`, `transport_records`, `gps_tracking`, `devices`, `device_assignments`, and `weight_readings` are used by the backend. The internal `counters` collection generates permanent IDs. GPS and weight histories remain separate records associated with their resolved transport.

## API

All responses use `{ "success": true, "message": "...", "data": ... }` or the matching error envelope.

- `GET|POST /api/sites`, `GET|PUT|DELETE /api/sites/<site_id>`
- `GET|POST /api/vehicles`, `GET|PUT|DELETE /api/vehicles/<vehicle_id>`, `GET /api/vehicles/<vehicle_id>/history`
- `PUT /api/vehicles/<vehicle_id>/site` with `{ "site_id": "CON-0002" }` assigns or reassigns an eligible vehicle to an active site. It returns `409` while an active transport exists. Completing a verified transport still releases the site assignment.
- `GET|POST /api/drivers`, `GET|PUT|DELETE /api/drivers/<driver_id>`
- `GET|POST /api/facilities`, `GET|PUT|DELETE /api/facilities/<facility_id>`
- `GET|POST /api/waste`, `GET|PUT|DELETE /api/waste/<waste_id>`
- `GET|POST /api/transports`, `GET /api/transports/<transport_id>`
- `POST /api/transports/<transport_id>/load|start|arrive|verify|complete|weight`
- `GET|POST /api/gps`, `GET /api/gps?transport_id=<transport_id>`
- `GET|POST /api/devices`, `GET|PUT|DELETE /api/devices/<device_id>`
- `POST /api/device/gps`, `POST /api/device/weight`, `GET /api/device/weight?transport_id=<transport_id>`
- `GET /api/facilities/recommend?waste_type=Concrete&latitude=17.385&longitude=78.4867`
- `GET /api/dashboard`, `GET /health`

Transport status is enforced as `Created -> Loaded -> In Transit -> Arrived -> Verified -> Completed`. A weight mismatch is marked `Mismatch` and cannot be completed automatically.

Vehicle site assignment is stored on the vehicle; each transport keeps its original `site_id` and `vehicle_id`. Vehicle document updates atomically reserve an active transport, preventing concurrent API requests from creating multiple active transports for that vehicle. Devices have a permanent `device_id` and can be reassigned to an unclaimed vehicle through `PUT /api/devices/<device_id>` with `{"vehicle_id":"VEH-0002"}`. Reassignment updates the one-to-one `device_assignments` claims and vehicle references while leaving transport and telemetry history unchanged. Existing duplicate device/vehicle assignments must be resolved before reassignment is enabled on an existing database.

## ESP32 Phase 1 Prototype

Set a local shared demo token in `backend/.env`:

```text
DEVICE_API_TOKEN=replace-with-a-long-random-local-demo-token
DEVICE_ONLINE_WINDOW_SECONDS=90
```

The device telemetry routes require that value in the `X-Device-Token` header. This shared token is for a trusted local prototype, not production authentication. Register the hardware ID against its vehicle, for example `POST /api/devices` with `{"device_id":"DEV-0002","vehicle_id":"VEH-0001"}`. Set the permanent device ID and the same token in `firmware/esp32/esp32_waste_monitor.ino`; the firmware does not contain a vehicle, site, facility, or transport ID.

The sketch posts GPS to `/api/device/gps` and raw HX711 counts to `/api/device/weight`. Raw readings use `calibration_status: "NOT_SET"` and `weight_kg: null`; they do not update transport kilogram weights. Existing calibrated `weight_kg` requests remain supported.

The server resolves the device's current vehicle assignment and its single active transport. Telemetry requests must not include assignment fields (`vehicle_id`, `transport_id`, `site_id`, or `facility_id`); ambiguous, inconsistent, closed, or incomplete assignments are rejected.

Example GPS request:

```json
{
	"device_id": "DEV-0002",
	"latitude": 17.385,
	"longitude": 78.4867,
	"satellites": 8,
	"gps_fix": true,
	"timestamp": "2026-09-29T10:00:00Z",
	"source": "device"
}
```

Example raw HX711 request:

```json
{
	"device_id": "DEV-0002",
	"raw_value": -209177,
	"calibration_status": "NOT_SET",
	"weight_kg": null,
	"timestamp": "2026-09-29T10:00:00Z"
}
```

Send both requests with `X-Device-Token: <DEVICE_API_TOKEN>`. If a GPS fix is unavailable, send `gps_fix: false` with null coordinates; no route origin is created from that point.

Flask already binds to `0.0.0.0` on `PORT` (5000 by default). Find the computer's Wi-Fi IPv4 address with `ipconfig`, set `FLASK_BASE_URL` in the sketch to `http://<computer-lan-ip>:5000`, and allow that port through the local firewall. Do not use `localhost` in the sketch.

For Arduino IDE, select **ESP32 Dev Module**, set upload speed to **115200**, and use the detected serial port. Install **ArduinoJson**, **TinyGPSPlus**, **HX711**, **Adafruit SSD1306**, and **Adafruit GFX Library** through Library Manager. The sketch uses UART2 (ESP32 RX 25/TX 26), HX711 DT/SCK 18/19, and OLED SDA/SCL 21/22. Wi-Fi credentials and the Flask URL are compile-time constants in the sketch.

## Testing

```powershell
.venv\Scripts\python.exe -m unittest discover -s backend\tests -p "test_*.py"
```

The tests cover common responses, weight verification, lifecycle restrictions, vehicle reuse semantics, device routing, invalid/inactive device rejection, weight history, facility filtering, and GPS route compliance. Full MongoDB integration testing requires a running MongoDB instance.
