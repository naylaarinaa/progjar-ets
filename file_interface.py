import os
import logging
import base64
from glob import glob

class FileInterface:
    def __init__(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.files_dir = os.path.normpath(os.path.join(base_dir, 'files'))
        os.makedirs(self.files_dir, mode=0o755, exist_ok=True)
        if not os.path.isdir(self.files_dir):
            raise RuntimeError(f"Failed to access directory: {self.files_dir}")
        self.original_dir = os.getcwd()
        logging.info(f"File storage initialized at: {self.files_dir}")

    def _chdir(self, to_files=True):
        os.chdir(self.files_dir if to_files else self.original_dir)

    def upload(self, params=[]):
        try:
            self._chdir(True)
            filename, filedata = params
            with open(filename, 'wb') as f:
                f.write(base64.b64decode(filedata))
            return {'status':'OK', 'data':f"{filename} uploaded successfully"}
        except Exception as e:
            return {'status':'ERROR', 'data':str(e)}
        finally:
            self._chdir(False)

    def delete(self, params=[]):
        try:
            self._chdir(True)
            os.remove(params[0])
            return {'status':'OK', 'data':f"{params[0]} deleted successfully"}
        except Exception as e:
            return {'status':'ERROR', 'data':str(e)}
        finally:
            self._chdir(False)

    def list(self, params=[]):
        try:
            self._chdir(True)
            return {'status':'OK', 'data': glob('*.*')}
        except Exception as e:
            return {'status':'ERROR', 'data':str(e)}
        finally:
            self._chdir(False)

    def get(self, params=[]):
        try:
            self._chdir(True)
            filename = params[0]
            if not filename:
                return None
            with open(filename, 'rb') as f:
                encoded = base64.b64encode(f.read()).decode()
            return {'status':'OK', 'data_namafile': filename, 'data_file': encoded}
        except Exception as e:
            return {'status':'ERROR', 'data': str(e)}
        finally:
            self._chdir(False)

if __name__ == '__main__':
    f = FileInterface()
    print(f.list())
    print(f.get(['pokijan.jpg']))
