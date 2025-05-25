import socket
import logging
import sys
from multiprocessing import Pool
from file_protocol import FileProtocol

class HandleClientProcess:
    def __init__(self):
        self.protocol = FileProtocol()

    def __call__(self, connection_address):
        connection, _ = connection_address
        buffer = ''
        while True:
            chunk = connection.recv(8192)
            if not chunk:
                break
            buffer += chunk.decode()
            if "\r\n\r\n" in buffer:
                response = self.protocol.proses_string(buffer.strip()) + "\r\n\r\n"
                connection.sendall(response.encode())
                break
        connection.close()
        return True

class ProcessPoolServer:
    def __init__(self, host='0.0.0.0', port=6666, max_workers=5):
        self.address = (host, port)
        self.pool = Pool(processes=max_workers)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self):
        logging.warning(f"server berjalan di ip address {self.address} dengan process pool (max_workers={self.pool._processes})")
        self.server_socket.bind(self.address)
        self.server_socket.listen()
        client_handler = HandleClientProcess()
        while True:
            connection, client_addr = self.server_socket.accept()
            logging.warning(f"connection from {client_addr}")
            self.pool.apply_async(client_handler, args=((connection, client_addr),))

def main():
    max_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    ProcessPoolServer(max_workers=max_workers).run()

if __name__ == "__main__":
    main()
