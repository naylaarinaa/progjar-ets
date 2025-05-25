import socket
import multiprocessing
import base64
import os
import json
import signal
import sys

SERVER_ADDRESS = ('localhost', 1111)
FILES_DIR = 'files'
os.makedirs(FILES_DIR, exist_ok=True)

manager = multiprocessing.Manager()
success_counter = manager.Value('i', 0)
fail_counter = manager.Value('i', 0)


def send_response(conn, response_dict):
    response_json = json.dumps(response_dict) + "\r\n\r\n"
    try:
        conn.sendall(response_json.encode())
    except Exception:
        pass


def handle_client(conn_fileno):
    try:
        conn = socket.socket(fileno=conn_fileno)
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

            with success_counter.get_lock():
                success_counter.value += 1

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

            with success_counter.get_lock():
                success_counter.value += 1

            response = {'status': 'OK', 'data_file': encoded_data}

        elif command == 'STATUS':
            with success_counter.get_lock(), fail_counter.get_lock():
                response = {
                    'status': 'OK',
                    'server_success': success_counter.value,
                    'server_failed': fail_counter.value
                }

        elif command == 'RESET':
            with success_counter.get_lock(), fail_counter.get_lock():
                success_counter.value = 0
                fail_counter.value = 0
            response = {'status': 'OK', 'message': 'Server counters reset'}

        elif command == 'DELETE':
            if len(parts) < 2:
                raise ValueError("DELETE requires filename")
            filename = parts[1]
            filepath = os.path.join(FILES_DIR, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                with success_counter.get_lock():
                    success_counter.value += 1
                response = {'status': 'OK', 'data': f'{filename} deleted'}
            else:
                raise FileNotFoundError(f"{filename} not found on server")

        elif command == 'LIST':
            files = os.listdir(FILES_DIR)
            response = {'status': 'OK', 'data': files}

        else:
            raise ValueError(f"Unknown command: {command}")

    except Exception as e:
        with fail_counter.get_lock():
            fail_counter.value += 1
        response = {'status': 'ERROR', 'message': str(e)}
    finally:
        send_response(conn, response)
        conn.close()
    return True


def start_server(worker_count=10):
    print(f"Server listening at {SERVER_ADDRESS}")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(SERVER_ADDRESS)
        s.listen(100)

        pool = multiprocessing.Pool(worker_count)
        print(f"Started pool with {worker_count} worker processes")

        try:
            while True:
                conn, addr = s.accept()
                client_ip, client_port = addr

                # Hanya cek IP client, jangan cek port client
                if client_ip == '127.0.0.1':
                    fileno = conn.fileno()
                    conn.detach()
                    pool.apply_async(handle_client, (fileno,))
                else:
                    print(f"Rejected connection from {addr}")
                    conn.close()
        except KeyboardInterrupt:
            print("Server shutting down...")
        finally:
            pool.close()
            pool.join()


if __name__ == '__main__':
    start_server(worker_count=10)
