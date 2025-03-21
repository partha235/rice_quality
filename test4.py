import socket
import threading
import cv2
import time

# Server configuration
HOST = ""     # Listen on all available interfaces
PORT = 8080

# Start the socket server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(5)  # Up to 5 clients
print(f"Serving on http://192.168.1.4:{PORT}")

# Initialize webcam
camera = cv2.VideoCapture(0)

# Stream frames to clients
def stream_video(client_socket):
    try:
        while True:
            ret, frame = camera.read()
            if not ret:
                break
            
            # Encode the frame to JPEG
            _, buffer = cv2.imencode('.jpg', frame)
            frame_bytes = buffer.tobytes()

            # Send the frame as binary data
            client_socket.sendall(
                b"HTTP/1.1 200 OK\r\n"
                b"Content-Type: multipart/x-mixed-replace; boundary=frame\r\n"
                b"\r\n"
            )
            
            # Send frame
            client_socket.sendall(
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )

            time.sleep(0.05)  # Control frame rate
    except BrokenPipeError:
        print("Client disconnected.")
    finally:
        client_socket.close()

# Handle client connections
def handle_client(client_socket, addr):
    print(f"Connected by {addr}")
    request = client_socket.recv(1024).decode()

    if "GET /video" in request:  # Serve video stream
        stream_video(client_socket)
    else:  # Serve the HTML page
        html = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Webcam Stream</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin: 0; padding: 0; background: #f4f4f4; }
                header { background: #4CAF50; color: white; padding: 20px; }
                img { width: 80%; max-width: 800px; margin: 20px; border: 5px solid #4CAF50; box-shadow: 0 0 10px #888; }
            </style>
        </head>
        <body>
            <header>
                <h1>Grain Quality Robot - Webcam Stream</h1>
            </header>
            <img src="/video" alt="Webcam Stream">
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
