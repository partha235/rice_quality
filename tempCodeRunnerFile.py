HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8080

# Start the server
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((HOST, PORT))
server_socket.listen(5)  # Up to 5 clients
print(f"Serving on http://{HOST}:{PORT}")