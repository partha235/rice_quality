import socket
import threading
import cv2
import json
import time
import random
import RPi.GPIO as GPIO

# ========== GPIO SETUP ==========
GPIO.setmode(GPIO.BCM)

# Define motor pins
IN1 = 17  # Left Motor Forward
IN2 = 18  # Left Motor Backward
IN3 = 22  # Right Motor Forward
IN4 = 23  # Right Motor Backward

MOTOR_PINS = [IN1, IN2, IN3, IN4]
for pin in MOTOR_PINS:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)

def stop():
    for pin in MOTOR_PINS:
        GPIO.output(pin, GPIO.LOW)

def move_forward():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)

def move_backward():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)

def turn_left():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)

def turn_right():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)

# ========== SERVER SETUP ==========
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

def get_sensor_data():
    return random.randint(400, 1000)

def handle_robot_command(client_socket, command):
    print(f"Robot Command Received: {command}")
    command = command.strip().upper()

    if command == "UP":
        move_forward()
    elif command == "DOWN":
        move_backward()
    elif command == "LEFT":
        turn_left()
    elif command == "RIGHT":
        turn_right()
    else:
        stop()

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
        pass
    client_socket.close()

def handle_sensor_data(client_socket):
    sensor_value = get_sensor_data()
    response = json.dumps({"value": sensor_value})
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
            html = open("index.html").read().replace("{LOCAL_IP}", LOCAL_IP).replace("{PORT}", str(PORT))
            client_socket.sendall(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html\r\n"
                b"Access-Control-Allow-Origin: *\r\n\r\n" +
                html.encode()
            )
    except:
        pass
    client_socket.close()

try:
    while True:
        client, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(client, addr)).start()
except KeyboardInterrupt:
    print("\nShutting down...")
    camera.release()
    GPIO.cleanup()
    server_socket.close()
