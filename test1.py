import socket
import threading
import json
import random
import time

# Server configuration
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8080

# Start the server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(5)  # Up to 5 clients
print(f"Serving on http://{HOST}:{PORT}")

# Function to simulate CO₂ sensor data (replace with real sensor values)
def get_sensor_data():
    return random.randint(400, 1000)  # Simulated CO₂ values in ppm

# Handle client connections
def handle_client(client_socket, addr):
    print(f"Connected by {addr}")
    
    request = client_socket.recv(1024).decode()
    if "GET /data" in request:  # Handle data endpoint
        sensor_value = get_sensor_data()
        response = json.dumps({"value": sensor_value})
        
        client_socket.sendall(
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Access-Control-Allow-Origin: *\r\n"
            b"\r\n" +
            response.encode()
        )
    else:  # Serve the HTML page
        html = """
        <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>GQR - Grain Quality Robot</title>
                <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
                <style>
                     body {
                        font-family: Arial, sans-serif;
                        margin: 0;
                        padding: 0;
                        background: #f4f4f4;
                        color: #333;
                        line-height: 1.6;
                    }
                    header {
                        background: #4CAF50;
                        color: #fff;
                        padding: 20px;
                        text-align: center;
                    }
                    main {
                        padding: 20px;
                        text-align: center;
                    }
                    footer {
                        background: #333;
                        color: #fff;
                        text-align: center;
                        padding: 10px;
                        position: fixed;
                        bottom: 0;
                        width: 100%;
                    }
                    .btn {
                        display: inline-block;
                        padding: 10px 20px;
                        color: #fff;
                        background: #4CAF50;
                        text-decoration: none;
                        border-radius: 5px;
                        transition: 0.3s;
                    }
                    .btn:hover {
                        background: #45a049;
                    }
                    canvas {
                        width: 100%;
                        max-width: 600px;
                        height: 400px;
                        display: block;
                        margin: 20px auto;
                    }
                </style>
            </head>
            <body>
                <header>
                    <h1>Grain Quality Robot (GQR)</h1>
                    <p>Automated system for detecting and ensuring the quality of grains</p>
                </header>
                <p>Real-time CO<sub>2</sub> Monitoring</p>
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
                    function updateChart(data) {
                        if (chart.data.labels.length > 20) {
                            chart.data.labels.shift();
                            chart.data.datasets[0].data.shift();
                        }
                        chart.data.labels.push(new Date().toLocaleTimeString());
                        chart.data.datasets[0].data.push(data);
                        chart.update();
                    }
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

# Accept incoming connections in separate threads
while True:
    client_socket, addr = server_socket.accept()
    threading.Thread(target=handle_client, args=(client_socket, addr)).start()
