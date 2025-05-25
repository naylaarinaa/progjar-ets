import socket
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from file_protocol import FileProtocol

class ClientHandler:
    def __init__(self, client_socket, client_address):
        self.client_socket = client_socket
        self.protocol = FileProtocol()

    def run(self):
        buffer = ''
        while True:
            chunk = self.client_socket.recv(8192)
            if not chunk:
                break
            buffer += chunk.decode()
            if "\r\n\r\n" in buffer:
                response = self.protocol.proses_string(buffer.strip()) + "\r\n\r\n"
                self.client_socket.sendall(response.encode())
                break
        self.client_socket.close()
        return True

class ThreadPoolServer:
    def __init__(self, host='0.0.0.0', port=6666, max_workers=5):
        self.address = (host, port)
        self.thread_pool = ThreadPoolExecutor(max_workers=max_workers)
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self):
        logging.warning(f"server berjalan di ip address {self.address} dengan thread pool (max_workers={self.thread_pool._max_workers})")
        self.server_socket.bind(self.address)
        self.server_socket.listen()
        while True:
            client_sock, client_addr = self.server_socket.accept()
            logging.warning(f"connection from {client_addr}")
            self.thread_pool.submit(ClientHandler(client_sock, client_addr).run)

def main():
    max_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    ThreadPoolServer(max_workers=max_workers).run()

if __name__ == "__main__":
    main()
