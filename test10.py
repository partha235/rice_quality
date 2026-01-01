import socket
import threading
import json
import RPi.GPIO as GPIO
import spidev
import cv2
import time

# ========== GPIO Motor Setup ==========
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

MOTOR_PINS = {
    "forward": (17, 18),
    "backward": (22, 23),
    "left": (17, 23),
    "right": (18, 22),
}

MOTOR_PWM = {}

# Setup and initialize PWM
for pins in set(pin for pair in MOTOR_PINS.values() for pin in pair):
    GPIO.setup(pins, GPIO.OUT)
    MOTOR_PWM[pins] = GPIO.PWM(pins, 1000)  # 1kHz
    MOTOR_PWM[pins].start(0)

def stop_motors():
    for pwm in MOTOR_PWM.values():
        pwm.ChangeDutyCycle(0)

def control_motor(command, speed=100):
    stop_motors()
    if command in MOTOR_PINS:
        for pin in MOTOR_PINS[command]:
            MOTOR_PWM[pin].ChangeDutyCycle(speed)

# ========== MQ135 Sensor Setup ==========
spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 1350000

def read_mq135(channel=0):
    adc = spi.xfer2([1, (8 + channel) << 4, 0])
    value = ((adc[1] & 3) << 8) + adc[2]
    return value

def get_sensor_data():
    raw = read_mq135(0)
    co2_ppm = int((raw / 1024.0) * 5000)
    return co2_ppm

# ========== Video Stream Setup (OpenCV with USB Cam) ==========
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
            client_socket.sendall(
                b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" +
                frame_data + b"\r\n"
            )
        except:
            break

# ========== Web Interface ==========
def serve_html(client_socket):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Raspberry Pi Robot</title>
        <script>
            let commandTimeout;
            let isHolding = false;

            function sendCommand(command, speed = 100) {
                fetch('/command', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ command, speed })
                });

                clearTimeout(commandTimeout);

                if (!isHolding && command !== 'stop') {
                    commandTimeout = setTimeout(() => sendCommand('stop', 0), 150);
                }
            }

            function holdCommand(command, speed = 100) {
                isHolding = true;
                sendCommand(command, speed);
            }

            function releaseCommand() {
                isHolding = false;
                clearTimeout(commandTimeout);
                sendCommand('stop', 0);
            }

            function updateChart(data) {
                document.getElementById('chart').innerText = "CO₂: " + data + " ppm";
            }

            setInterval(() => {
                fetch('/data')
                .then(res => res.json())
                .then(data => updateChart(data.value));
            }, 1000);
        </script>
    </head>
    <body>
        <h1>Raspberry Pi Robot</h1>
        <img src="/video" width="640">
        <div>
            <button onmousedown="holdCommand('forward', 80)" onmouseup="releaseCommand()">⬆️</button><br>
            <button onmousedown="holdCommand('left', 60)" onmouseup="releaseCommand()">⬅️</button>
            <button onmousedown="holdCommand('right', 60)" onmouseup="releaseCommand()">➡️</button><br>
            <button onmousedown="holdCommand('backward', 80)" onmouseup="releaseCommand()">⬇️</button>
        </div>
        <h2 id="chart">CO₂: Loading...</h2>
    </body>
    </html>
    """
    client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + html.encode())

# ========== Request Handler ==========
def handle_sensor_data(client_socket):
    response = json.dumps({"value": get_sensor_data()})
    client_socket.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n" + response.encode())

def handle_client(client_socket, addr):
    try:
        request = client_socket.recv(1024).decode()
        if "GET /video" in request:
            stream_video(client_socket)
        elif "GET /data" in request:
            handle_sensor_data(client_socket)
        elif "POST /command" in request:
            data = request.split('\r\n')[-1]
            command_data = json.loads(data)
            control_motor(command_data.get("command"), command_data.get("speed", 100))
            client_socket.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": "ok"}')
        elif "POST /stop" in request:
            stop_motors()
            client_socket.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n\r\n{"status": "stopped"}')
        else:
            serve_html(client_socket)
    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        client_socket.close()

# ========== Server Setup ==========
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind(('0.0.0.0', 8080))
server_socket.listen(5)

print("✅ Server running at http://<your_pi_ip>:8080")
try:
    while True:
        client, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(client, addr)).start()
except KeyboardInterrupt:
    print("🛑 Shutting down...")
    GPIO.cleanup()
    server_socket.close()
    camera.release()
