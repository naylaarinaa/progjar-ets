import os
import time
import base64
import socket
import json
import concurrent.futures
import csv
import subprocess
import signal

SERVER_IP = '127.0.0.1'
SERVER_PORT = 8888
USE_MULTIPROCESSING = False  # Pastikan tetap False agar tidak makan RAM

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

def run_client_workers(operation, filename, client_workers):
    func = client_upload if operation == 'upload' else client_download
    results = []
    executor_cls = concurrent.futures.ProcessPoolExecutor if USE_MULTIPROCESSING else concurrent.futures.ThreadPoolExecutor
    with executor_cls(max_workers=client_workers) as executor:
        futures = []
        for _ in range(client_workers):
            futures.append(executor.submit(func, filename))
            time.sleep(0.01)  # Tambahkan delay agar tidak overload
        for i, f in enumerate(concurrent.futures.as_completed(futures), 1):
            sukses, durasi, tp, info = f.result()
            results.append((sukses, durasi, tp, info))
            status_str = 'SUKSES' if sukses else 'GAGAL'
            print(f"  Worker #{i}: {status_str}, Durasi: {durasi:.3f}s, Throughput: {int(tp)} B/s, Info: {info}")
    return results

def main():
    operasi_list = ['upload', 'download']
    volume_list = [10, 50, 100]
    client_worker_pool_list = [1, 5, 50]
    server_worker_pool_list = [1, 5, 50]

    os.makedirs('test_files', exist_ok=True)
    for volume in volume_list:
        generate_dummy_file(f'test_files/file_{volume}mb.bin', volume)

    # Baca hasil sebelumnya kalau ada
    seen_tests = set()
    nomor = 1
    if os.path.exists('stress_test_results.csv'):
        with open('stress_test_results.csv', 'r') as f_csv:
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

    with open('stress_test_results.csv', 'a', newline='') as f_csv:
        writer = csv.writer(f_csv)
        if os.stat('stress_test_results.csv').st_size == 0:
            writer.writerow(header)

        for server_workers in server_worker_pool_list:
            print(f"\n=== Testing dengan Server Workers = {server_workers} ===")

            server_process = subprocess.Popen(
                ['python3', 'file_server.py', '--workers', str(server_workers)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

            time.sleep(1.5)

            try:
                for operasi in operasi_list:
                    for volume in volume_list:
                        filename = f'test_files/file_{volume}mb.bin'
                        for client_workers in client_worker_pool_list:
                            key = (operasi, volume, client_workers, server_workers)
                            if key in seen_tests:
                                print(f"✅ Skipping test sudah ada: {key}")
                                continue
                            if client_workers >50 and volume > 100:
                                print(f"⚠️  Skipping berat: Volume={volume}MB, Clients={client_workers}")
                                continue

                            print(f"\nTest #{nomor}: Operasi={operasi.upper()}, Volume={volume}MB, Client Workers={client_workers}, Server Workers={server_workers}")
                            results = run_client_workers(operasi, filename, client_workers)

                            sukses = sum(1 for r in results if r[0])
                            gagal = client_workers - sukses
                            avg_time = (sum(r[1] for r in results if r[0]) / sukses) if sukses else 0
                            avg_tp = (sum(r[2] for r in results if r[0]) / sukses) if sukses else 0

                            row = [
                                nomor,
                                operasi,
                                volume,
                                client_workers,
                                server_workers,
                                round(avg_time, 3),
                                int(avg_tp),
                                sukses,
                                gagal,
                                sukses,  # Dummy data, bisa diganti jika ada log server
                                gagal
                            ]

                            writer.writerow(row)
                            f_csv.flush()
                            nomor += 1
            finally:
                server_process.send_signal(signal.SIGINT)
                server_process.wait()
                time.sleep(1)

    print("\nStress test selesai, hasil sudah ditambahkan ke stress_test_results.csv")

if __name__ == '__main__':
    main()