import socket
import threading
import cv2
import json
import time
import random

# Get local IP address dynamically
def get_local_ip():
    """Returns the local IP address of the server."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Google's public DNS
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print("Failed to get local IP:", e)
        return "127.0.0.1"  # Fallback to localhost

# Server configuration
PORT = 8080
LOCAL_IP = get_local_ip()

# Start the socket server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((LOCAL_IP, PORT))
server_socket.listen(5)

print(f"\n🔥 Server running at:")
print(f"👉 http://{LOCAL_IP}:{PORT}\n")

# Initialize webcam
camera = cv2.VideoCapture(0)

# Function to simulate CO₂ sensor data
def get_sensor_data():
    """Generates random CO₂ values in ppm"""
    return random.randint(400, 1000)  # Simulated CO₂ values

# Handle robot movement commands
def handle_robot_command(client_socket, command):
    """Handle robot movement commands."""
    print(f"Robot Command Received: {command}")
    
    # Here you can add the motor control logic
    # e.g., send signals to ESP32 or Arduino via GPIO/PWM

    # Send acknowledgment
    client_socket.sendall(
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Access-Control-Allow-Origin: *\r\n"
        b"\r\n"
        b'{"status": "command received"}'
    )
    client_socket.close()

# Stream frames to clients
def stream_video(client_socket):
    """Stream webcam video frames to the client."""
    try:
        client_socket.sendall(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
            b"\r\n"
        )
        
        while camera.isOpened():
            ret, frame = camera.read()
            if not ret:
                break

            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            client_socket.sendall(
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )

            time.sleep(0.05)  # Control frame rate

    except (BrokenPipeError, ConnectionResetError):
        print("Client disconnected.")
    finally:
        client_socket.close()

# Handle individual sensor data requests
def handle_sensor_data(client_socket):
    """Handle single request for sensor data."""
    try:
        sensor_value = get_sensor_data()  # Generate a random CO₂ value
        response = json.dumps({"value": sensor_value})

        client_socket.sendall(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Access-Control-Allow-Origin: *\r\n"
            b"\r\n" +
            response.encode()
        )
    except (BrokenPipeError, ConnectionResetError):
        print("Sensor client disconnected.")
    finally:
        client_socket.close()

# Handle client requests
def handle_client(client_socket, addr):
    print(f"Connected by {addr}")
    try:
        request = client_socket.recv(1024).decode()

        if "GET /video" in request:
            stream_video(client_socket)
        elif "GET /data" in request:
            handle_sensor_data(client_socket)
        elif "POST /command" in request:
            # Extract command from the request
            command = request.split('\r\n')[-1]
            handle_robot_command(client_socket, command)
        else:
            # HTML content with robot control buttons
            html = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Grain Quality Robot - Webcam & Control</title>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <style>
                    body {{ font-family: Arial, sans-serif; text-align: center; background: #f4f4f4; margin: 0; padding: 0; }}
                    header {{ background: #4CAF50; color: white; padding: 20px; }}
                    img {{ width: 80%; max-width: 800px; margin: 20px; border: 5px solid #4CAF50; box-shadow: 0 0 10px #888; }}
                    canvas {{ width: 80%; max-width: 800px; height: 400px; margin: 20px auto; display: block; }}
                    button {{ font-size: 24px; padding: 15px 30px; margin: 10px; }}
                    .controls {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; width: 300px; margin: 20px auto; }}
                </style>
            </head>
            <body>
                <header>
                    <h1>Grain Quality Robot - Webcam & Control</h1>
                </header>

                <h2>Access from another device</h2>
                <a href="http://{LOCAL_IP}:{PORT}" target="_blank">
                    📱 Open on iPhone: http://{LOCAL_IP}:{PORT}
                </a>

                <h2>Live Webcam Stream</h2>
                <img src="/video" alt="Webcam Stream">

                <h2>Robot Controls</h2>
                <div class="controls">
                    <button onclick="sendCommand('UP')">⬆️ Forward</button>
                    <button onclick="sendCommand('LEFT')">⬅️ Left</button>
                    <button onclick="sendCommand('RIGHT')">➡️ Right</button>
                    <button onclick="sendCommand('DOWN')">⬇️ Backward</button>
                </div>

                <h2>Real-time CO₂ Monitoring</h2>
                <canvas id="chart"></canvas>

                <script>
                    const ctx = document.getElementById('chart').getContext('2d');
                    const chart = new Chart(ctx, {{
                        type: 'line',
                        data: {{
                            labels: [],
                            datasets: [{{
                                label: 'CO₂ (ppm)',
                                borderColor: 'rgb(75, 192, 192)',
                                backgroundColor: 'rgba(75, 192, 192, 0.2)',
                                data: [],
                                fill: true
                            }}]
                        }},
                        options: {{
                            responsive: true,
                            scales: {{
                                x: {{ display: true, title: {{ display: true, text: 'Time' }} }},
                                y: {{ display: true, title: {{ display: true, text: 'CO₂ (ppm)' }} }}
                            }}
                        }}
                    }});

                    // Update chart with new data
                    function updateChart(data) {{
                        if (chart.data.labels.length > 20) {{
                            chart.data.labels.shift();
                            chart.data.datasets[0].data.shift();
                        }}
                        chart.data.labels.push(new Date().toLocaleTimeString());
                        chart.data.datasets[0].data.push(data);
                        chart.update();
                    }}

                    // Send robot command to the server
                    function sendCommand(command) {{
                        fetch('/command', {{
                            method: 'POST',
                            body: command
                        }})
                        .then(response => response.json())
                        .catch(err => console.error('Error:', err));
                    }}

                    // Fetch data every second
                    setInterval(() => {{
                        fetch('/data')
                            .then(response => response.json())
                            .then(data => updateChart(data.value))
                            .catch(err => console.error('Error:', err));
                    }}, 1000);
                </script>
            </body>
            </html>
            """

            # Send the response
            response = (
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: text/html\r\n"
                b"Access-Control-Allow-Origin: *\r\n"
                b"\r\n" +
                html.encode()
            )
            client_socket.sendall(response)

    except (BrokenPipeError, ConnectionResetError):
        print("Client disconnected.")
    finally:
        client_socket.close()

# Accept incoming connections
try:
    while True:
        client_socket, addr = server_socket.accept()
        threading.Thread(target=handle_client, args=(client_socket, addr)).start()
except KeyboardInterrupt:
    print("\nShutting down server...")
    camera.release()
    server_socket.close()
