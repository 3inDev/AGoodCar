#include <Arduino.h>
#include <WiFi.h>
#include <WiFiUdp.h>

const char* AP_SSID = "aGTDepzai2";
const char* AP_PASS = "ftcagt20262"; 
WiFiUDP udp;
const uint16_t UDP_PORT = 4210;

const int IN1 = 25; 
const int IN2 = 26;
const int IN3 = 27; 
const int IN4 = 14;

unsigned long lastPacketMs = 0;
const unsigned long FAILSAFE_MS = 500;

void motorStop() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
}

void motorForward() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}

void motorBackward() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}

void motorLeft() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
}

void motorRight() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
}

void executeCommand(char cmd) {
  switch (cmd) {
    case 'F': motorForward(); break;
    case 'B': motorBackward(); break;
    case 'L': motorLeft(); break;
    case 'R': motorRight(); break;
    case 'S': 
    default:  motorStop(); break; 
  }
}

void setup() {
  Serial.begin(115200);
  
  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);
  
  motorStop(); 

  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASS);
  
  IPAddress ip = WiFi.softAPIP();
  Serial.print("AP IP: ");
  Serial.println(ip);
  
  udp.begin(UDP_PORT);
  Serial.print("Listening on port: ");
  Serial.println(UDP_PORT);
  
  lastPacketMs = millis();
}

void loop() {
  int packetSize = udp.parsePacket();
  if (packetSize > 0) {
    char buffer[16];
    int len = udp.read(buffer, sizeof(buffer)-1);
    if (len > 0) {
      buffer[len] = '\0';
      char cmd = buffer[0];
      executeCommand(cmd);
      lastPacketMs = millis();
      Serial.print("CMD: ");
      Serial.println(cmd);
    }
  }
  if (millis() - lastPacketMs > FAILSAFE_MS) {
    motorStop();
  }
}