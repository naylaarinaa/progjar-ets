import os
import json
import base64
import socket
import threading
from glob import glob

class FileInterface:

    def list(self, params=[]):
        try:
            filelist = glob('*.*')
            return dict(status='OK', data=filelist)
        except Exception as e:
            return dict(status='ERROR', data=str(e))

    def get(self,params=[]):
        try:
            filename = params[0]
            if (filename == ''):
                return None
            fp = open(f"{filename}",'rb')
            isifile = base64.b64encode(fp.read()).decode()
            return dict(status='OK',data_namafile=filename,data_file=isifile)
        except Exception as e:
            return dict(status='ERROR',data=str(e))

    def upload(self, params=[]):
        try:
            filename = params[0]
            filedata = params[1]
            with open(filename, 'wb') as f:
                f.write(base64.b64decode(filedata))
            return dict(status='OK', data=f"File '{filename}' berhasil diupload.")
        except Exception as e:
            return dict(status='ERROR', data=str(e))

    def delete(self, params=[]):
        try:
            filename = params[0]
            os.remove(filename)
            return dict(status='OK', data=f"File '{filename}' berhasil dihapus.")
        except Exception as e:
            return dict(status='ERROR', data=str(e))


def handle_client(conn, addr, interface):
    print(f"Client connected: {addr}")
    data = ""
    while True:
        d = conn.recv(1024)
        if not d:
            break
        data += d.decode()
        if "\r\n\r\n" in data:
            break

    try:
        parts = data.strip().split(' ', 2)
        command = parts[0].upper()
        if command == 'LIST':
            result = interface.list()
        elif command == 'GET':
            result = interface.get([parts[1]])
        elif command == 'UPLOAD':
            result = interface.upload([parts[1], parts[2]])
        elif command == 'DELETE':
            result = interface.delete([parts[1]])
        else:
            result = dict(status='ERROR', data='Unknown command')
    except Exception as e:
        result = dict(status='ERROR', data=str(e))

    response = json.dumps(result) + "\r\n\r\n"
    conn.sendall(response.encode())
    conn.close()


def run_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(('0.0.0.0', 6666))
    server.listen(5)
    print("Server listening on port 6666...")
    interface = FileInterface()

    while True:
        conn, addr = server.accept()
        client_thread = threading.Thread(target=handle_client, args=(conn, addr, interface))
        client_thread.start()


if __name__ == '__main__':
    run_server()