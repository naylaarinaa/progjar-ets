import json
import logging
import shlex
from file_interface import FileInterface

class FileProtocol:
    def __init__(self):
        self.file = FileInterface()

    def proses_string(self, data=''):
        try:
            header, body = (data.split('\r\n', 1) + [''])[:2]
            parts = shlex.split(header.lower())
            cmd, params = parts[0], parts[1:]
            logging.warning(f"memproses request: {cmd}")

            if cmd == 'upload':
                res = getattr(self.file, cmd)([params[0], body.strip()])
            else:
                res = getattr(self.file, cmd)(params)

            return json.dumps(res)
        except Exception as e:
            logging.error(e)
            return json.dumps({'status': 'ERROR', 'data': 'request tidak dikenali'})

if __name__ == '__main__':
    fp = FileProtocol()
    print(fp.proses_string("LIST"))
    print(fp.proses_string("GET pokijan.jpg"))
