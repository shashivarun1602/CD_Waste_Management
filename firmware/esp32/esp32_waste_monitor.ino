#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>
#include <HX711.h>
#include <HTTPClient.h>
#include <TinyGPSPlus.h>
#include <WiFi.h>
#include <Wire.h>
#include <time.h>

const char *WIFI_SSID = "YOUR_WIFI_SSID";
const char *WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char *FLASK_BASE_URL = "http://192.168.1.10:5000";
const char *DEVICE_ID = "DEV-0002";
const char *DEVICE_API_TOKEN = "REPLACE_WITH_DEVICE_API_TOKEN";

constexpr int GPS_RX_PIN = 25;
constexpr int GPS_TX_PIN = 26;
constexpr int HX711_DT_PIN = 18;
constexpr int HX711_SCK_PIN = 19;
constexpr int OLED_SDA_PIN = 21;
constexpr int OLED_SCL_PIN = 22;
constexpr unsigned long TELEMETRY_INTERVAL_MS = 5000;

HardwareSerial gpsSerial(2);
TinyGPSPlus gps;
HX711 scale;
Adafruit_SSD1306 display(128, 64, &Wire, -1);

unsigned long lastTelemetryAt = 0;
unsigned long lastWifiAttemptAt = 0;
long latestRawValue = 0;
bool hasRawValue = false;
bool displayReady = false;

String timestampUtc() {
  struct tm timeInfo;
  if (!getLocalTime(&timeInfo, 10)) {
    return "";
  }
  char value[25];
  strftime(value, sizeof(value), "%Y-%m-%dT%H:%M:%SZ", &timeInfo);
  return String(value);
}

void connectWifi() {
  if (WiFi.status() == WL_CONNECTED || millis() - lastWifiAttemptAt < 10000) {
    return;
  }
  lastWifiAttemptAt = millis();
  Serial.printf("Connecting to Wi-Fi: %s\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void sendJson(const char *path, JsonDocument &payload) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("HTTP skipped: Wi-Fi is offline");
    return;
  }

  String body;
  serializeJson(payload, body);
  HTTPClient http;
  const String url = String(FLASK_BASE_URL) + path;
  if (!http.begin(url)) {
    Serial.printf("HTTP begin failed: %s\n", url.c_str());
    return;
  }
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Token", DEVICE_API_TOKEN);
  const int status = http.POST(body);
  Serial.printf("POST %s -> HTTP %d\n", path, status);
  if (status > 0) {
    Serial.println(http.getString());
  } else {
    Serial.printf("HTTP error: %s\n", http.errorToString(status).c_str());
  }
  http.end();
}

void sendGps() {
  const bool hasFix = gps.location.isValid() && gps.location.age() < 3000;
  const uint32_t satellites = gps.satellites.isValid() ? gps.satellites.value() : 0;

  StaticJsonDocument<384> payload;
  payload["device_id"] = DEVICE_ID;
  payload["gps_fix"] = hasFix;
  payload["satellites"] = satellites;
  payload["timestamp"] = timestampUtc();
  payload["source"] = "device";
  if (hasFix) {
    payload["latitude"] = gps.location.lat();
    payload["longitude"] = gps.location.lng();
  } else {
    payload["latitude"] = nullptr;
    payload["longitude"] = nullptr;
  }
  sendJson("/api/device/gps", payload);
}

void sendRawWeight() {
  if (!scale.is_ready()) {
    Serial.println("HX711 not ready; raw reading skipped");
    return;
  }

  latestRawValue = scale.read();
  hasRawValue = true;

  StaticJsonDocument<320> payload;
  payload["device_id"] = DEVICE_ID;
  payload["raw_value"] = latestRawValue;
  payload["calibration_status"] = "NOT_SET";
  payload["weight_kg"] = nullptr;
  payload["timestamp"] = timestampUtc();
  sendJson("/api/device/weight", payload);
}

void updateDisplay() {
  if (!displayReady) {
    return;
  }
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0, 0);
  display.printf("%s  %s\n", DEVICE_ID, WiFi.status() == WL_CONNECTED ? "ONLINE" : "OFFLINE");
  display.println("Transport: server");
  if (gps.location.isValid() && gps.location.age() < 3000) {
    display.printf("GPS FIX  SAT: %u\n", gps.satellites.isValid() ? gps.satellites.value() : 0);
    display.printf("%.5f\n%.5f\n", gps.location.lat(), gps.location.lng());
  } else {
    display.println("GPS: NO FIX");
  }
  display.printf("RAW: %s", hasRawValue ? String(latestRawValue).c_str() : "waiting");
  display.setCursor(0, 56);
  display.print("Calibration: NOT SET");
  display.display();
}

void setup() {
  Serial.begin(115200);
  gpsSerial.begin(9600, SERIAL_8N1, GPS_RX_PIN, GPS_TX_PIN);
  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN);
  displayReady = display.begin(SSD1306_SWITCHCAPVCC, 0x3C);
  scale.begin(HX711_DT_PIN, HX711_SCK_PIN);

  WiFi.setSleep(false);
  connectWifi();
  configTime(0, 0, "pool.ntp.org", "time.nist.gov");
  Serial.printf("Device %s; Flask endpoint %s\n", DEVICE_ID, FLASK_BASE_URL);
}

void loop() {
  while (gpsSerial.available()) {
    gps.encode(gpsSerial.read());
  }

  connectWifi();
  if (millis() - lastTelemetryAt >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryAt = millis();
    sendGps();
    sendRawWeight();
  }
  updateDisplay();
  delay(10);
}