import os
import time
import base64
import socket
import json
import csv
import subprocess
import signal
import multiprocessing

SERVER_IP = '127.0.0.1'
SERVER_PORT = 1111  # PORT disamakan dengan server

def generate_dummy_file(filename, size_mb):
    if os.path.exists(filename) and os.path.getsize(filename) == size_mb * 1024 * 1024:
        return
    print(f"Generating {filename} ({size_mb} MB)...")
    with open(filename, 'wb') as f:
        f.write(os.urandom(size_mb * 1024 * 1024))

def send_command(command_str):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.connect((SERVER_IP, SERVER_PORT))
        sock.sendall((command_str + "\r\n\r\n").encode())
        data_received = ''
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data_received += chunk.decode()
            if "\r\n\r\n" in data_received:
                break
        return json.loads(data_received.split("\r\n\r\n")[0])
    except Exception as e:
        return {'status': 'ERROR', 'data': str(e)}
    finally:
        sock.close()

def client_upload(filename):
    try:
        with open(filename, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode()
    except Exception as e:
        return False, 0, 0, f"File read error: {e}"

    start = time.time()
    command = f"UPLOAD {os.path.basename(filename)} {encoded}"
    result = send_command(command)
    end = time.time()

    duration = end - start
    file_size = os.path.getsize(filename)
    throughput = file_size / duration if duration > 0 else 0

    if result.get('status') == 'OK':
        return True, duration, throughput, 'Upload successful'
    else:
        return False, duration, 0, f"Upload failed: {result.get('data', 'Unknown error')}"

def client_download(filename):
    start = time.time()
    result = send_command(f"GET {os.path.basename(filename)}")
    end = time.time()

    duration = end - start
    if result.get('status') == 'OK':
        try:
            data = base64.b64decode(result['data_file'])
        except Exception as e:
            return False, duration, 0, f"Decode error: {e}"
        size = len(data)
        throughput = size / duration if duration > 0 else 0
        return True, duration, throughput, 'Download successful'
    else:
        return False, duration, 0, f"Download failed: {result.get('data', 'Unknown error')}"

def client_worker(args):
    operation, filename = args
    if operation == 'upload':
        return client_upload(filename)
    elif operation == 'download':
        return client_download(filename)
    else:
        return False, 0, 0, f"Unknown operation: {operation}"

def run_client_workers(operation, filename, client_workers):
    results = []
    with multiprocessing.Pool(client_workers) as pool:
        args_list = [(operation, filename)] * client_workers
        async_results = pool.map_async(client_worker, args_list)
        for i, res in enumerate(async_results.get(), 1):
            sukses, durasi, tp, info = res
            results.append(res)
            status_str = 'SUKSES' if sukses else 'GAGAL'
            print(f"  Worker #{i}: {status_str}, Durasi: {durasi:.3f}s, Throughput: {int(tp)} B/s, Info: {info}")
            time.sleep(0.01)
    return results

def main():
    operasi_list = ['upload', 'download']
    volume_list = [10, 50, 100]
    client_worker_pool_list = [1, 5, 50]
    server_worker_pool_list = [1, 5, 50]

    os.makedirs('test_files', exist_ok=True)
    for volume in volume_list:
        generate_dummy_file(f'test_files/file_{volume}mb.bin', volume)

    seen_tests = set()
    nomor = 1
    if os.path.exists('pp_stress_test_results.csv'):
        with open('pp_stress_test_results.csv', 'r') as f_csv:
            reader = csv.DictReader(f_csv)
            for row in reader:
                key = (
                    row['Operasi'],
                    int(row['Volume(MB)']),
                    int(row['Client Worker Pool']),
                    int(row['Server Worker Pool'])
                )
                seen_tests.add(key)
                nomor = max(nomor, int(row['Nomor']) + 1)

    header = [
        "Nomor", "Operasi", "Volume(MB)", "Client Worker Pool",
        "Server Worker Pool", "Waktu Total/Client(s)",
        "Throughput/Client(Bytes/s)",
        "Client Worker Sukses", "Client Worker Gagal",
        "Server Worker Sukses", "Server Worker Gagal"
    ]

    with open('pp_stress_test_results.csv', 'a', newline='') as f_csv:
        writer = csv.writer(f_csv)
        if os.stat('pp_stress_test_results.csv').st_size == 0:
            writer.writerow(header)

        for server_workers in server_worker_pool_list:
            print(f"\n=== Testing dengan Server Workers = {server_workers} ===")

            server_process = subprocess.Popen(
                ['python', 'pp_file_server.py', str(server_workers)]
            )
            time.sleep(2)  # Tunggu server siap

            try:
                for operation in operasi_list:
                    for volume in volume_list:
                        key = (operation, volume, 1, server_workers)
                        if key in seen_tests:
                            print(f"Skip test {key}")
                            continue

                        filename = f'test_files/file_{volume}mb.bin'

                        print(f"\n#{nomor}. Operasi: {operation.upper()}, Volume: {volume} MB, "
                              f"Client Worker Pool: 1, Server Worker Pool: {server_workers}")

                        results = run_client_workers(operation, filename, 1)

                        waktu_total = sum(r[1] for r in results)
                        throughput_total = sum(r[2] for r in results)
                        client_sukses = sum(1 for r in results if r[0])
                        client_gagal = sum(1 for r in results if not r[0])

                        # Dapatkan status server (worker sukses/gagal)
                        status = send_command('STATUS')
                        if status.get('status') == 'OK':
                            server_sukses = status.get('server_success', 0)
                            server_gagal = status.get('server_failed', 0)
                        else:
                            server_sukses = -1
                            server_gagal = -1

                        writer.writerow([
                            nomor, operation.upper(), volume,
                            1, server_workers,
                            round(waktu_total, 3),
                            int(throughput_total),
                            client_sukses, client_gagal,
                            server_sukses, server_gagal
                        ])
                        f_csv.flush()
                        nomor += 1
            finally:
                server_process.send_signal(signal.SIGINT)
                server_process.wait()
                time.sleep(2)

if __name__ == '__main__':
    main()
