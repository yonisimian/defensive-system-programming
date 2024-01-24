import random
from typing import Tuple, List
import binascii # TODO: remove
import socket
from enum import Enum
import struct

VERSION = 1

class Op(Enum):
    SAVE = 100
    RESTORE = 200
    DELETE = 201
    LIST = 202

class Status(Enum):
    SUCCESS_RESTORE = 210
    SUCCESS_LIST = 211
    SUCCESS_SAVE = 212
    ERROR_NO_FILE = 1001
    ERROR_NO_CLIENT = 1002
    ERROR_GENERAL = 1003

class Payload:
    def __init__(self, size: int, payload: bytes):
        if not (0 <= size <= 0xFFFFFFFF):
            raise ValueError("payload.size is out of range for uint32_t.")
        
        self.size = size
        self.payload = payload

class Request:
    def __init__(self, user_id: int, version: int, op: Op, name_len: int, filename: str, payload: Payload):
        if not (0 <= user_id <= 0xFFFFFFFF):
            raise ValueError(f"user_id {user_id} is out of range for uint32_t.")
        if not (0 <= version <= 0xFF):
            raise ValueError(f"version {version} is out of range for uint8_t.")
        if not (0 <= op.value <= 0xFF):
            raise ValueError(f"op.value {op.value} is out of range for uint8_t.")
        if not (0 <= name_len <= 0xFFFF):
            raise ValueError(f"name_len {name_len} is out of range for uint16_t.")
        
        self.user_id = user_id
        self.version = version
        self.op = op.value
        self.name_len = name_len
        self.filename = filename
        self.payload = payload

class Response:
    def __init__(self, version: int, status: Status, name_len: int, filename: str, payload: Payload):
        self.version = version
        self.status = status
        self.name_len = name_len
        self.filename = filename
        self.payload = payload

class FileHandler:
    SERVER_INFO_FILE = "server.info"
    BACKUP_INFO_FILE = "backup.info"
    def __init__(self):
        self.server_info_file = self.SERVER_INFO_FILE
        self.backup_info_file = self.BACKUP_INFO_FILE

    def validate_ip(self, ip: str) -> bool:
        try:
            socket.inet_aton(ip)
            return True
        except socket.error:
            return False

    def validate_port(self, port: str) -> bool:
        return 0 <= int(port) <= 65535

    def read_server_info(self) -> Tuple[str, int]:
        try:
            with open(self.server_info_file, 'r') as file:
                ip_address, port = file.readline().strip().split(':')
                if not self.validate_ip(ip_address):
                    raise ValueError("Invalid IP address.")
                if not self.validate_port(port):
                    raise ValueError("Invalid port number.")
                port = int(port)
        except FileNotFoundError:
            raise Exception(f"{self.server_info_file} file not found.")
        except ValueError as e:
            raise Exception(f"An error occurred: {str(e)}")
        except Exception as e:
            raise Exception(f"An error occurred: {str(e)}")
        return ip_address, port

    def read_backup_info(self) -> List[str]:
        try:
            with open(self.backup_info_file, 'r') as file:
                filenames = [line.strip() for line in file]
        except FileNotFoundError:
            raise Exception(f"{self.backup_info_file} file not found.")
        except Exception as e:
            raise Exception(f"An error occurred: {str(e)}")
        return filenames

class UniqueIDGenerator:
    def __init__(self):
        self.generated_ids = set()

    def generate_unique_id(self) -> int:
        while True:
            unique_id = random.randint(0, 0xFFFFFFFF)
            if unique_id not in self.generated_ids:
                self.generated_ids.add(unique_id)
                return unique_id

class Client:
    def __init__(self, ip_address: str, port: int):
        self.ip_address = ip_address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
        self.socket.connect((self.ip_address, self.port))

    def send_request(self, request: Request):
        self.socket.send(self.pack_request(request))
        data = self.socket.recv(1024)
        data += self.socket.recv(1024)
        data += self.socket.recv(1024)
        data += self.socket.recv(1024)
        print(f'received response: {binascii.hexlify(data)}')
        response = self.unpack_response(data)
        self.print_response(response)

    def __del__(self):
        self.socket.close()

    def pack_request(self, request: Request) -> bytes:
        # Convert the filename to bytes
        filename_bytes = request.filename.encode('utf-8')

        if not (0 <= len(filename_bytes) <= 0xFFFF):
            raise ValueError("Filename length is out of range.")
        if not (0 <= len(request.payload.payload) <= 0xFFFFFFFF):
            raise ValueError("Payload size is out of range.")
        
        print(request.__dict__)
        print(request.payload.__dict__)
        
        # Pack the request data into a bytes object
        request_data = struct.pack(
            f'<I B B H {len(filename_bytes)}s I {len(request.payload.payload)}s',
            request.user_id,
            request.version,
            request.op,
            len(filename_bytes),
            filename_bytes,
            len(request.payload.payload),
            request.payload.payload
        )

        print(binascii.hexlify(request_data))

        return request_data

    def unpack_response(self, data: bytes) -> Response:
        # Unpack the version and status from the first part of the response
        version, status, name_len = struct.unpack('<B H H', data[:5])

        # Calculate the start and end indices of the filename in the data
        filename_start = 5
        filename_end = filename_start + name_len

        # Unpack the filename from the data
        print(f"filename_start: {filename_start}, filename_end: {filename_end}")
        print(f"data slice: {data[filename_start:filename_end]}")

        filename = data[filename_start:filename_end].decode('ascii')

        # Unpack the payload size from the data
        if len(data) < filename_end + 4:
            payload_obj = None
        else:
            payload_size = struct.unpack('<I', data[filename_end:filename_end+4])[0]

            # Unpack the payload from the data
            payload_start = filename_end + 4
            payload_end = payload_start + payload_size
            payload = data[payload_start:payload_end]

            # Create a Payload object
            payload_obj = Payload(payload_size, payload)

        # Create a Response object
        response = Response(version, Status(status), name_len, filename, payload_obj)

        return response

    def print_response(self, response: Response):
        print(f"Version: {response.version}")
        print(f"Status: {response.status}")
        print(f"Name length: {response.name_len}")
        print(f"Filename: {response.filename}")
        if (response.payload is not None):
            print(f"Payload size: {response.payload.size}")
            print(f"Payload: {response.payload.payload}")

def generate_save_request(user_id: int, filename: str, payload: bytes) -> Request:
    payload_obj = Payload(len(payload), payload)
    request = Request(user_id, VERSION, Op.SAVE, len(filename), filename, payload_obj)

    return request

def main():
    uniqueIDGenerator = UniqueIDGenerator() 
    unique_id = uniqueIDGenerator.generate_unique_id()
    unique_id = 53764

    reader = FileHandler()
    ip_address, port = reader.read_server_info()
    filenames = reader.read_backup_info()

    client = Client(ip_address, port)
    save_request = generate_save_request(unique_id, "abcdefghi", b'a')
    client.send_request(save_request)

if __name__ == "__main__":
    main()