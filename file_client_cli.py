import socket
import json
import base64
import logging

server_address=('172.16.16.101',6666)

def send_command(command_str=""):
    global server_address
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect(server_address)
    logging.warning(f"connecting to {server_address}")
    try:
        logging.warning(f"sending message ")
        sock.sendall((command_str + "\r\n\r\n").encode())
        
        data_received = "" #empty string
        while True:
            #socket does not receive all data at once, data comes in part, need to be concatenated at the end of process
            data = sock.recv(4096)
            if data:
                #data is not empty, concat with previous content
                data_received += data.decode()
                if "\r\n\r\n" in data_received:
                    break
            else:
                # no more data, stop the process by break
                break
        # at this point, data_received (string) will contain all data coming from the socket
        # to be able to use the data_received as a dict, need to load it using json.loads()
        hasil = json.loads(data_received.split("\r\n\r\n")[0])
        logging.warning("data received from server:")
        return hasil
    except Exception as e:
        logging.warning(f"error during data receiving: {e}")
        return dict(status='ERROR', data=str(e))
    finally:
        sock.close()

def remote_list():
    hasil = send_command("LIST")
    if (hasil['status']=='OK'):
        print("daftar file : ")
        for nmfile in hasil['data']:
            print(f"- {nmfile}")
        return True
    else:
        print("Gagal:", hasil.get('data'))
        return False

def remote_get(filename=""):
    hasil = send_command(f"GET {filename}")
    if (hasil['status']=='OK'):
        #proses file dalam bentuk base64 ke bentuk bytes
        namafile= hasil['data_namafile']
        isifile = base64.b64decode(hasil['data_file'])
        with open(namafile,'wb') as fp:
            fp.write(isifile)
        print(f"File {filename} berhasil didownload.")
        return True
    else:
        print("Gagal:", hasil.get('data'))
        return False

def remote_upload(filename=""):
    try:
        with open(filename, 'rb') as fp:
            data_base64 = base64.b64encode(fp.read()).decode()
    except FileNotFoundError:
        print(f"Upload gagal: file '{filename}' tidak ditemukan.")
        return

    hasil = send_command(f"UPLOAD {filename} {data_base64}")
    if (hasil['status']=='OK'):
        print(hasil.get('data'))
    else:
        print("Upload gagal:", hasil.get('data'))

def remote_delete(filename=""):
    hasil = send_command(f"DELETE {filename}")
    if (hasil['status']=='OK'):
        print(hasil.get('data'))
    else:
        print("Delete gagal:", hasil.get('data'))

if __name__=='__main__':
    while True:
        cmd = input("Command: LIST | GET <filename> | UPLOAD <filename> | DELETE <filename> | QUIT\n>>> ").strip()
        if cmd.upper() == "LIST":
            remote_list()
        elif cmd.upper().startswith("GET "):
            remote_get(cmd[4:].strip())
        elif cmd.upper().startswith("UPLOAD "):
            remote_upload(cmd[7:].strip())
        elif cmd.upper().startswith("DELETE "):
            remote_delete(cmd[7:].strip())
        elif cmd.upper() == "QUIT":
            print("Keluar.")
            break
        else:
            print("Perintah tidak dikenali.")