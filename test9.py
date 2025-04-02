import socket
import threading
import json
import time
import random
import RPi.GPIO as GPIO
import spidev
import cv2
import numpy as np
from io import BytesIO

# Raspberry Pi GPIO setup
GPIO.setmode(GPIO.BCM)

# Define motor control pins
MOTOR_PINS = {
    "forward": (17, 18),
    "backward": (22, 23),
    "left": (17, 23),
    "right": (18, 22),
}

# Initialize motor pins
for pin_set in MOTOR_PINS.values():
    for pin in pin_set:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.LOW)

# Function to stop all motors
def stop_motors():
    for pin_set in MOTOR_PINS.values():
        for pin in pin_set:
            GPIO.output(pin, GPIO.LOW)

# Function to control motor movement
def control_motor(command):
    stop_motors()
    if command in MOTOR_PINS:
        for pin in MOTOR_PINS[command]:
            GPIO.output(pin, GPIO.HIGH)

# Initialize SPI for MCP3008
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

# Read analog data from MQ-135 sensor
def read_mq135(channel=0):
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    value = ((adc[1] & 3) << 8) + adc[2]
    return value

# Convert ADC value to approximate CO₂ level
def get_sensor_data():
    raw_value = read_mq135(0)
    co2_ppm = int((raw_value / 1024.0) * 5000)
    return co2_ppm

# OpenCV Video Capture
cap = cv2.VideoCapture(0)

# Function to stream video
def stream_video(client_socket):
    client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n")
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Rotate frame 90 degrees to the right
        frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        
        _, jpeg = cv2.imencode('.jpg', frame)
        frame_bytes = jpeg.tobytes()
        client_socket.sendall(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")

# Function to handle client requests
def handle_client(client_socket, addr):
    try:
        request = client_socket.recv(1024).decode()

        if "GET /video" in request:
            stream_video(client_socket)
        elif "GET /data" in request:
            handle_sensor_data(client_socket)
        elif "POST /command" in request:
            command = request.split('\r\n')[-1]
            control_motor(command)
            client_socket.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": "ok"}')
        elif "POST /stop" in request:
            stop_motors()
            client_socket.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": "stopped"}')
        else:
            serve_html(client_socket)
    except Exception as e:
        print("Error handling request:", e)
    finally:
        client_socket.close()

# Serve the control panel HTML page
def serve_html(client_socket):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Raspberry Pi Robot</title>
        <script>
            function sendCommand(command) {
                fetch('/command', {
                    method: 'POST',
                    body: command
                });
            }
            function stop() {
                fetch('/stop', {
                    method: 'POST'
                });
            }
            function updateChart(data) {
                let chart = document.getElementById('chart');
                chart.innerText = "CO₂: " + data + " ppm";
            }
            setInterval(() => {
                fetch('/data').then(res => res.json()).then(data => updateChart(data.value));
            }, 1000);
        </script>
    </head>
    <body>
        <h1>Raspberry Pi Robot</h1>
        <img src="/video" width="640">
        <div>
            <button onmousedown="sendCommand('forward')" onmouseup="stop()">⬆️</button>
            <button onmousedown="sendCommand('left')" onmouseup="stop()">⬅️</button>
            <button onmousedown="sendCommand('right')" onmouseup="stop()">➡️</button>
            <button onmousedown="sendCommand('backward')" onmouseup="stop()">⬇️</button>
        </div>
        <h2 id="chart">CO₂: Loading...</h2>
    </body>
    </html>
    """
    client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html.encode())

# Function to handle sensor data request
def handle_sensor_data(client_socket):
    response = json.dumps({"value": get_sensor_data()})
    client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + response.encode())

# Start the server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('0.0.0.0', 8080))
server_socket.listen(5)

print("Server running on Raspberry Pi...")
try:
    while True:
        client_socket, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(client_socket, addr)).start()
except KeyboardInterrupt:
    print("Shutting down...")
    cap.release()
    cv2.destroyAllWindows()
    GPIO.cleanup()
    server_socket.close()
