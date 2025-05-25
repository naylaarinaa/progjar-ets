import socket
import threading
import base64
import os
import json
from concurrent.futures import ThreadPoolExecutor

SERVER_ADDRESS = ('localhost', 8888)
FILES_DIR = 'server_files'
os.makedirs(FILES_DIR, exist_ok=True)

success_counter = 0
fail_counter = 0
counter_lock = threading.Lock()

server_pool_size = 10  # default, nanti bisa diubah oleh client

def send_response(conn, response_dict):
    response_json = json.dumps(response_dict) + "\r\n\r\n"
    conn.sendall(response_json.encode())

def handle_client(conn, addr):
    global success_counter, fail_counter, server_pool_size
    try:
        data = b""
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if b"\r\n\r\n" in data:
                break

        message = data.decode(errors='ignore').strip()
        parts = message.split(' ', 2)

        if not parts or len(parts) < 1:
            raise ValueError("Invalid command format")

        command = parts[0].upper()
        response = {}

        if command == 'UPLOAD':
            if len(parts) < 3:
                raise ValueError("UPLOAD requires filename and file content")
            filename = parts[1]
            encoded_data = parts[2]

            try:
                decoded_data = base64.b64decode(encoded_data.encode('utf-8'), validate=True)
            except Exception:
                raise ValueError("Invalid base64 encoding")

            with open(os.path.join(FILES_DIR, filename), 'wb') as f:
                f.write(decoded_data)

            with counter_lock:
                success_counter += 1

            response = {'status': 'OK', 'message': f'{filename} uploaded'}

        elif command == 'GET':
            if len(parts) < 2:
                raise ValueError("GET requires filename")
            filename = parts[1]
            filepath = os.path.join(FILES_DIR, filename)
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"{filename} not found on server")

            with open(filepath, 'rb') as f:
                encoded_data = base64.b64encode(f.read()).decode('utf-8')

            with counter_lock:
                success_counter += 1

            response = {'status': 'OK', 'data_namafile': filename, 'data_file': encoded_data}

        elif command == 'STATUS':
            with counter_lock:
                response = {
                    'status': 'OK',
                    'server_success': success_counter,
                    'server_failed': fail_counter
                }

        elif command == 'RESET':
            with counter_lock:
                success_counter = 0
                fail_counter = 0
            response = {'status': 'OK', 'message': 'Server counters reset'}

        elif command == 'DELETE':
            if len(parts) < 2:
                raise ValueError("DELETE requires filename")
            filename = parts[1]
            filepath = os.path.join(FILES_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                response = {'status': 'OK', 'data': f'{filename} deleted'}
            else:
                raise FileNotFoundError(f"{filename} not found on server")

        elif command == 'LIST':
            files = os.listdir(FILES_DIR)
            response = {'status': 'OK', 'data': files}

        elif command == 'SETPOOL':
            if len(parts) < 2:
                raise ValueError("SETPOOL requires a number")
            try:
                new_size = int(parts[1])
                if new_size < 1:
                    raise ValueError("Server pool size must be >= 1")
                server_pool_size = new_size
                response = {'status': 'OK', 'message': f"Server pool size set to {server_pool_size}"}
            except ValueError:
                raise ValueError("Invalid server pool size")

        else:
            raise ValueError(f"Unknown command: {command}")

    except Exception as e:
        with counter_lock:
            fail_counter += 1
        response = {'status': 'ERROR', 'message': str(e)}
    finally:
        send_response(conn, response)
        conn.close()

def start_server():
    global server_pool_size
    print(f"Server listening at {SERVER_ADDRESS}")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(SERVER_ADDRESS)
        s.listen(100)
        with ThreadPoolExecutor(max_workers=server_pool_size) as executor:
            while True:
                conn, addr = s.accept()
                executor.submit(handle_client, conn, addr)

if __name__ == '__main__':
    start_server()