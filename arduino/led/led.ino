#include <WiFi.h>
#include <ESPAsyncWebServer.h>

const char* ssid = "XRT";
const char* password = "1m@n1D10t";

// Pin for the built-in LED on ESP32 (may vary depending on the board)
const int LED_PIN = 2;

AsyncWebServer server(80);

void setup() {
  Serial.begin(115200);

  // Set LED pin as output
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW); // Initially turn off LED

  // Connect to Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.println("Connecting to WiFi...");
  }
  Serial.println("Connected to WiFi");

  Serial.print("ESP32 IP Address: ");
  Serial.println(WiFi.localIP());

  // Route to turn on the LED
  server.on("/led/on", HTTP_GET, [](AsyncWebServerRequest *request){
    digitalWrite(LED_PIN, HIGH); // Turn on LED
    request->send(200, "text/plain", "LED turned on");
  });

  // Route to turn off the LED
  server.on("/led/off", HTTP_GET, [](AsyncWebServerRequest *request){
    digitalWrite(LED_PIN, LOW); // Turn off LED
    request->send(200, "text/plain", "LED turned off");
  });

  // Start server
  server.begin();
}

void loop() {
  // Nothing to do here
}
