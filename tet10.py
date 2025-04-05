import socket
import threading
import RPi.GPIO as GPIO
import json
import cv2

# ===== Get Local IP (accurate on LAN) =====
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print("Failed to get local IP:", e)
        return "127.0.0.1"

LOCAL_IP = get_local_ip()
PORT = 8080

# ===== GPIO Setup =====
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

MOTOR_PINS = {
    "forward": (17, 18),
    "backward": (22, 23),
    "left": (17, 23),
    "right": (18, 22),
}

MOTOR_PWM = {}

for pin in set(pin for pins in MOTOR_PINS.values() for pin in pins):
    GPIO.setup(pin, GPIO.OUT)
    MOTOR_PWM[pin] = GPIO.PWM(pin, 1000)
    MOTOR_PWM[pin].start(0)

def stop_motors():
    for pwm in MOTOR_PWM.values():
        pwm.ChangeDutyCycle(0)

def control_motor(command, speed=100):
    stop_motors()
    if command in MOTOR_PINS:
        for pin in MOTOR_PINS[command]:
            MOTOR_PWM[pin].ChangeDutyCycle(speed)

# ===== Video Streaming =====
camera = cv2.VideoCapture(0)

def stream_video(client_socket):
    client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace; boundary=frame\r\n\r\n")
    while True:
        ret, frame = camera.read()
        if not ret:
            continue
        _, jpeg = cv2.imencode('.jpg', frame)
        frame_data = jpeg.tobytes()
        try:
            client_socket.sendall(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame_data + b"\r\n")
        except:
            break

# ===== HTML Page =====
def serve_html(client_socket):
    html = """
    <html>
    <head>
        <title>Robot Control</title>
        <script>
            let timeout;
            let hold = false;

            function sendCommand(cmd, speed=100) {
                fetch('/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ command: cmd, speed: speed })
                });
                clearTimeout(timeout);
                if (!hold && cmd !== "stop") {
                    timeout = setTimeout(() => sendCommand("stop", 0), 200);
                }
            }

            function holdCommand(cmd, speed=100) {
                hold = true;
                sendCommand(cmd, speed);
            }

            function releaseCommand() {
                hold = false;
                clearTimeout(timeout);
                sendCommand("stop", 0);
            }
        </script>
    </head>
    <body>
        <h1>Robot Control</h1>
        <img src="/video" width="640"><br>
        <button onmousedown="holdCommand('forward')" onmouseup="releaseCommand()">⬆️</button><br>
        <button onmousedown="holdCommand('left')" onmouseup="releaseCommand()">⬅️</button>
        <button onmousedown="holdCommand('right')" onmouseup="releaseCommand()">➡️</button><br>
        <button onmousedown="holdCommand('backward')" onmouseup="releaseCommand()">⬇️</button>
    </body>
    </html>
    """
    client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html.encode())

# ===== Client Handler =====
def handle_client(client_socket, addr):
    try:
        request = client_socket.recv(1024).decode()
        if "GET /video" in request:
            stream_video(client_socket)
        elif "POST /command" in request:
            data = request.split('\r\n')[-1]
            cmd_data = json.loads(data)
            control_motor(cmd_data.get("command"), cmd_data.get("speed", 100))
            client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{\"status\": \"ok\"}")
        else:
            serve_html(client_socket)
    except Exception as e:
        print("Error:", e)
    finally:
        client_socket.close()

# ===== Server Setup =====
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((LOCAL_IP, PORT))
server_socket.listen(5)

print(f"\n🚀 Server running at: http://{LOCAL_IP}:{PORT}/\n")

try:
    while True:
        client_socket, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(client_socket, addr)).start()
except KeyboardInterrupt:
    print("\n🛑 Shutting down...")
finally:
    GPIO.cleanup()
    server_socket.close()
    camera.release()
