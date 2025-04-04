import socket
import threading
import cv2
import json
import time
import random

# Server configuration
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8080

# Start the server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(5)  # Up to 5 clients
print(f"Serving on http://{HOST}:{PORT}")

# Initialize webcam
camera = cv2.VideoCapture(0)

# Function to simulate CO₂ sensor data (replace with real sensor values)
def get_sensor_data():
    """Generates random CO₂ values in ppm"""
    return random.randint(400, 1000)  # Simulated CO₂ values

# Stream frames to clients
def stream_video(client_socket):
    """Stream webcam video frames to the client."""
    try:
        client_socket.sendall(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
            b"\r\n"
        )
        
        while True:
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

    except BrokenPipeError:
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
    except BrokenPipeError:
        print("Sensor client disconnected.")
    finally:
        client_socket.close()

# Handle client requests
def handle_client(client_socket, addr):
    print(f"Connected by {addr}")
    request = client_socket.recv(1024).decode()

    if "GET /video" in request:
        stream_video(client_socket)
    elif "GET /data" in request:
        handle_sensor_data(client_socket)
    else:
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Webcam & Graph Stream</title>
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; background: #f4f4f4; margin: 0; padding: 0; }
                header { background: #4CAF50; color: white; padding: 20px; }
                img { width: 80%; max-width: 800px; margin: 20px; border: 5px solid #4CAF50; box-shadow: 0 0 10px #888; }
                canvas { width: 80%; max-width: 800px; height: 400px; margin: 20px auto; display: block; }
            </style>
        </head>
        <body>
            <header>
                <h1>Grain Quality Robot - Webcam & Graph</h1>
            </header>
            
            <h2>Live Webcam Stream</h2>
            <img src="/video" alt="Webcam Stream">

            <h2>Real-time CO₂ Monitoring</h2>
            <canvas id="chart"></canvas>

            <script>
                const ctx = document.getElementById('chart').getContext('2d');
                const chart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: [],
                        datasets: [{
                            label: 'CO₂ (ppm)',
                            borderColor: 'rgb(75, 192, 192)',
                            backgroundColor: 'rgba(75, 192, 192, 0.2)',
                            data: [],
                            fill: true
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            x: { display: true, title: { display: true, text: 'Time' } },
                            y: { display: true, title: { display: true, text: 'CO₂ (ppm)' } }
                        }
                    }
                });

                // Update chart with new data
                function updateChart(data) {
                    if (chart.data.labels.length > 20) {
                        chart.data.labels.shift();
                        chart.data.datasets[0].data.shift();
                    }
                    chart.data.labels.push(new Date().toLocaleTimeString());
                    chart.data.datasets[0].data.push(data);
                    chart.update();
                }

                // Fetch data every second
                setInterval(() => {
                    fetch('/data')
                        .then(response => response.json())
                        .then(data => updateChart(data.value))
                        .catch(err => console.error('Error:', err));
                }, 1000);
            </script>
        </body>
        </html>
        """

        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/html\r\n"
            b"Access-Control-Allow-Origin: *\r\n"
            b"\r\n" +
            html.encode()
        )
        client_socket.sendall(response)
        client_socket.close()

# Accept incoming connections
while True:
    client_socket, addr = server_socket.accept()
    threading.Thread(target=handle_client, args=(client_socket, addr)).start()
