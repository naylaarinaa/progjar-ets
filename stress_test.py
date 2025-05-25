import socket, json, base64, time, os
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import subprocess
import csv
from itertools import product

# --- FileClient dan fungsinya ---
class FileClient:
    def __init__(self, server_address='localhost:6666'):
        host, port = server_address.split(':') if isinstance(server_address, str) else server_address
        self.server_address = (host, int(port))

    def send_command(self, cmd=""):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.connect(self.server_address)
                sock.sendall(cmd.encode())
                data = b""
                while True:
                    chunk = sock.recv(8192)
                    if not chunk: break
                    data += chunk
                    if b"\r\n\r\n" in data:
                        break
                return json.loads(data.decode())
            except Exception as e:
                return {"status": "ERROR", "data": str(e)}

    def remote_list(self):
        return self.send_command("LIST\r\n\r\n")

    def remote_get(self, filename=""):
        res = self.send_command(f"GET {filename}\r\n\r\n")
        return base64.b64decode(res['data_file']) if res.get('status') == 'OK' else None

    def remote_upload(self, filename="", file_data=None):
        chunk_size = 10 * 1024 * 1024
        encoded = ''.join(base64.b64encode(file_data[i:i+chunk_size]).decode() for i in range(0, len(file_data), chunk_size))
        return self.send_command(f"UPLOAD {filename}\r\n{encoded}\r\n\r\n")

def generate_test_file(filename, size_mb):
    size_bytes = size_mb * 1024 * 1024
    if os.path.exists(filename) and os.path.getsize(filename) == size_bytes:
        return filename
    with open(filename, 'wb') as f:
        f.write(os.urandom(size_bytes))
    return filename

def upload_worker(client, size_mb, wid):
    src_file = f"file{size_mb}mb.bin"    # ubah di sini
    generate_test_file(src_file, size_mb)
    with open(src_file, 'rb') as f:
        data = f.read()
    start = time.time()
    res = client.remote_upload(f"testfile_{size_mb}mb.dat", data)
    client.remote_list()
    return {'success': res.get('status') == 'OK', 'time': time.time() - start, 'bytes': len(data), 'worker_id': wid}

def download_worker(client, size_mb, wid):
    start = time.time()
    data = client.remote_get(f"testfile_{size_mb}mb.dat")
    return {'success': data is not None, 'time': time.time() - start, 'bytes': len(data) if data else 0, 'worker_id': wid}

def run_test(server, op, size_mb, workers, use_proc_pool=False):
    exec_class = ProcessPoolExecutor if use_proc_pool else ThreadPoolExecutor
    func = upload_worker if op == 'upload' else download_worker
    client = FileClient(server)
    with exec_class(max_workers=workers) as ex:
        futures = [ex.submit(func, client, size_mb, i) for i in range(workers)]
        results = [f.result() for f in as_completed(futures)]
    success = sum(r['success'] for r in results)
    fail = workers - success
    total_bytes = sum(r['bytes'] for r in results if r['success'])
    max_time = max(r['time'] for r in results)
    throughput = total_bytes / max_time if max_time > 0 else 0
    return {'operation': op, 'file_size_mb': size_mb, 'client_workers': workers, 'successful': success,
            'failed': fail, 'total_time': max_time, 'throughput': throughput, 'total_bytes': total_bytes}

# --- Fungsi server dan client testing gabungan ---
def start_server(server_type, workers):
    script = 'file_server_tp.py' if server_type == 'thread' else 'file_server_pp.py'
    return subprocess.Popen(['python3', script, str(workers)])

def run_client_test(operation, server_address, file_size, workers, use_process_pool):
    cmd = [
        'python3', __file__,
        '--server', server_address,
        '--operation', operation,
        '--file-size', str(file_size),
        '--workers', str(workers)
    ]
    if use_process_pool:
        cmd.append('--use-process-pool')

    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return json.loads(result.stdout) if result.returncode == 0 else None
    except Exception as e:
        print(f"Client test failed: {e}")
        return None

def get_last_completed_test_id(csv_filename):
    if not os.path.exists(csv_filename):
        return 0
    with open(csv_filename, newline='') as csvfile:
        try:
            last = 0
            reader = csv.DictReader(csvfile)
            for row in reader:
                try:
                    test_id = int(row['Nomor'])
                    if test_id > last:
                        last = test_id
                except:
                    continue
            return last
        except:
            return 0

def main():
    import argparse
    parser = argparse.ArgumentParser(description='File Server Stress Test')
    parser.add_argument('--server', default='localhost:6666')
    parser.add_argument('--operation', choices=['upload', 'download'])
    parser.add_argument('--file-size', type=int, choices=[10, 50, 100])
    parser.add_argument('--workers', type=int, choices=[1, 5, 50])
    parser.add_argument('--use-process-pool', action='store_true')
    args = parser.parse_args()

    csv_filename = 'stress_test_results.csv'

    if args.operation and args.file_size and args.workers:
        result = run_test(args.server, args.operation, args.file_size, args.workers, args.use_process_pool)
        print(json.dumps(result, indent=2))
        return

    test_matrix = [(op, size, cw) for op in ['upload', 'download'] for size in [10, 50, 100] for cw in [1, 5, 50]]
    server_types = ['thread', 'process']
    server_workers = [1, 5, 50]

    last_completed_id = get_last_completed_test_id(csv_filename)

    file_exists = os.path.exists(csv_filename)
    with open(csv_filename, 'a', newline='') as csvfile:
        fieldnames = ['Nomor','Operasi','Volume','Jumlah client worker pool','Jumlah server worker pool',
                      'Waktu total per client','Throughput per client',
                      'Jumlah worker client sukses','Jumlah worker client gagal',
                      'Tipe server','Status server']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        test_id = 1
        for operation, file_size, c_workers in test_matrix:
            for s_type, s_workers in product(server_types, server_workers):
                if test_id <= last_completed_id:
                    print(f"Skipping test {test_id} (already completed)")
                    test_id += 1
                    continue

                print("\n" + "="*60)
                print(f"Running Test #{test_id}")
                print(f"Operation           : {operation.capitalize()}")
                print(f"File Size           : {file_size} MB")
                print(f"Client Workers      : {c_workers}")
                print(f"Server Type         : {s_type.capitalize()} Server")
                print(f"Server Worker Count : {s_workers}")
                print("="*60)

                subprocess.run(['pkill', '-f', 'file_server'], stderr=subprocess.DEVNULL)
                time.sleep(1)
                server_proc = start_server(s_type, s_workers)
                time.sleep(2)

                try:
                    result = run_client_test(operation, 'localhost:6666', file_size, c_workers, False)
                    if not result:
                        writer.writerow({
                            'Nomor': test_id,
                            'Operasi': operation,
                            'Volume': file_size,
                            'Jumlah client worker pool': c_workers,
                            'Jumlah server worker pool': s_workers,
                            'Jumlah worker client sukses': 0,
                            'Jumlah worker client gagal': c_workers,
                            'Tipe server': s_type,
                            'Status server': 'crash',
                            'Waktu total per client': '',
                            'Throughput per client': ''
                        })
                        csvfile.flush()
                        print("Result: Test failed or no response from client.")
                        test_id += 1
                        continue

                    server_status = 'sukses' if server_proc.poll() is None else 'crash'

                    writer.writerow({
                        'Nomor': test_id,
                        'Operasi': operation,
                        'Volume': file_size,
                        'Jumlah client worker pool': c_workers,
                        'Jumlah server worker pool': s_workers,
                        'Waktu total per client': result['total_time'],
                        'Throughput per client': result['throughput'],
                        'Jumlah worker client sukses': result['successful'],
                        'Jumlah worker client gagal': result['failed'],
                        'Tipe server': s_type,
                        'Status server': server_status,
                    })
                    csvfile.flush()

                    print(f"Result: Client Success={result['successful']} | Client Fail={result['failed']} | Server Status={server_status}")
                    print(f"Total Time          : {result['total_time']:.3f} sec")
                    print(f"Throughput          : {result['throughput'] / (1024*1024):.3f} MB/s")

                    test_id += 1
                finally:
                    server_proc.terminate()
                    server_proc.wait()
                    time.sleep(1)

if __name__ == '__main__':
    main()
