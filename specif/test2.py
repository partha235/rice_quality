import socket
import threading
import cv2
import json
import time
import math
import RPi.GPIO as GPIO
import Adafruit_ADS1x15

# ===== GPIO SETUP =====
GPIO.setmode(GPIO.BCM)
IN1, IN2, IN3, IN4 = 17, 18, 22, 23
MOTOR_PINS = [IN1, IN2, IN3, IN4]
for pin in MOTOR_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

def stop(): [GPIO.output(pin, GPIO.LOW) for pin in MOTOR_PINS]
def move_forward(): GPIO.output(IN1, GPIO.HIGH); GPIO.output(IN2, GPIO.LOW); GPIO.output(IN3, GPIO.HIGH); GPIO.output(IN4, GPIO.LOW)
def move_backward(): GPIO.output(IN1, GPIO.LOW); GPIO.output(IN2, GPIO.HIGH); GPIO.output(IN3, GPIO.LOW); GPIO.output(IN4, GPIO.HIGH)
def turn_left(): GPIO.output(IN1, GPIO.LOW); GPIO.output(IN2, GPIO.HIGH); GPIO.output(IN3, GPIO.HIGH); GPIO.output(IN4, GPIO.LOW)
def turn_right(): GPIO.output(IN1, GPIO.HIGH); GPIO.output(IN2, GPIO.LOW); GPIO.output(IN3, GPIO.LOW); GPIO.output(IN4, GPIO.HIGH)

# ===== CO₂ SENSOR SETUP (MQ135 with ADS1115) =====
adc = Adafruit_ADS1x15.ADS1115()
GAIN = 1
RL = 20.2     # kΩ
R0 = 34.0     # Calibrated in clean air
a = -2.769
b = 2.602

def get_voltage(channel=0):
    value = adc.read_adc(channel, gain=GAIN)
    return value * 4.096 / 32767

def get_rs(voltage):
    if voltage <= 0:
        return float('inf')
    return ((4.096 - voltage) / voltage) * RL

def get_ppm(rs):
    ratio = rs / R0
    ppm =400+( 10 ** ((math.log10(ratio) - b) / a))
    return max(0, round(ppm, 2))

def get_sensor_data():
    voltage = get_voltage()
    rs = get_rs(voltage)
    ppm = get_ppm(rs)
    print(f"Voltage: {voltage:.2f} V, RS: {rs:.2f} kΩ, CO₂: {ppm} ppm")
    return ppm

# ===== SERVER SETUP =====
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

PORT = 8080
LOCAL_IP = get_local_ip()
camera = cv2.VideoCapture(0)
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((LOCAL_IP, PORT))
server_socket.listen(5)
print(f"🌐 Access Robot at: http://{LOCAL_IP}:{PORT}")

# ===== HANDLE REQUESTS =====
def handle_robot_command(client_socket, command):
    command = command.strip().upper()
    print(f"Robot Command: {command}")
    if command == "UP": move_forward()
    elif command == "DOWN": move_backward()
    elif command == "LEFT": turn_left()
    elif command == "RIGHT": turn_right()
    else: stop()
    time.sleep(0.5)
    stop()
    client_socket.sendall(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Access-Control-Allow-Origin: *\r\n\r\n"
        b'{"status": "command received"}'
    )
    client_socket.close()

def stream_video(client_socket):
    try:
        client_socket.sendall(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n"
        )
        while camera.isOpened():
            ret, frame = camera.read()
            if not ret:
                break
            _, buffer = cv2.imencode('.jpg', frame)
            client_socket.sendall(
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" +
                buffer.tobytes() + b"\r\n"
            )
            time.sleep(0.05)
    except:
        print("Video stream stopped.")
    finally:
        client_socket.close()

def handle_sensor_data(client_socket):
    value = get_sensor_data()
    response = json.dumps({"value": value})
    client_socket.sendall(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Access-Control-Allow-Origin: *\r\n\r\n" +
        response.encode()
    )
    client_socket.close()

def handle_client(client_socket, addr):
    try:
        request = client_socket.recv(1024).decode()
        if "GET /video" in request:
            stream_video(client_socket)
        elif "GET /data" in request:
            handle_sensor_data(client_socket)
        elif "POST /command" in request:
            command = request.split('\r\n')[-1]
            handle_robot_command(client_socket, command)
        else:
            with open("index.html") as f:
                html = f.read().replace("{LOCAL_IP}", LOCAL_IP).replace("{PORT}", str(PORT))
            client_socket.sendall(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html\r\n"
                b"Access-Control-Allow-Origin: *\r\n\r\n" +
                html.encode()
            )
    except Exception as e:
        print("Client error:", e)
    finally:
        client_socket.close()

# ===== MAIN LOOP =====
try:
    while True:
        client, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(client, addr)).start()
except KeyboardInterrupt:
    print("Shutting down...")
    camera.release()
    GPIO.cleanup()
    server_socket.close()
