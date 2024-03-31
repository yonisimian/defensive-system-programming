"""
File: server.py
Author: Yehonatan Simian
Date: February 2024

+-----------------------------------------------------------------------------------+
|                      Defensive System Programming - Maman 15                      |
|                                                                                   |
|           "Nothing starts until you take action." - Sonic The Hedgehog            |
+-----------------------------------------------------------------------------------+

Description:
This module provides a server interface compatible with the requirements of maman 15.
The server can securely backup and retrieve files of a compatible client.
The protocol is over TCP and the data is sent in little endian format.

The client is capable of sending the following requests:
- Sign up
- Send a public key
- Sign in
- Send a file
- CRC valid
- CRC invalid
- CRC invalid for the 4th time

The server can respond with the following statuses:
- Sign up succeeded
- Sign up failed
- Public key received, senging AES key
- CRC valid
- Message received (responsing to 'CRC valid' or 'CRC invalid for the fourth time')
- Sign in allowed, sending AES key
- Sign in rejected (client needs to sign up again)
- General error

Copyright: All rights reserved (c) Yehonatan Simian 2024
"""

from typing import Tuple, List, Literal
from enum import Enum
from abc import ABC
import sqlite3
import random
import socket
import string
import struct
import base64
import time
import os
from Crypto.Hash import SHA256

VERSION = 4


# CRC-32 implementation


crctab = [
    0x00000000,
    0x04C11DB7,
    0x09823B6E,
    0x0D4326D9,
    0x130476DC,
    0x17C56B6B,
    0x1A864DB2,
    0x1E475005,
    0x2608EDB8,
    0x22C9F00F,
    0x2F8AD6D6,
    0x2B4BCB61,
    0x350C9B64,
    0x31CD86D3,
    0x3C8EA00A,
    0x384FBDBD,
    0x4C11DB70,
    0x48D0C6C7,
    0x4593E01E,
    0x4152FDA9,
    0x5F15ADAC,
    0x5BD4B01B,
    0x569796C2,
    0x52568B75,
    0x6A1936C8,
    0x6ED82B7F,
    0x639B0DA6,
    0x675A1011,
    0x791D4014,
    0x7DDC5DA3,
    0x709F7B7A,
    0x745E66CD,
    0x9823B6E0,
    0x9CE2AB57,
    0x91A18D8E,
    0x95609039,
    0x8B27C03C,
    0x8FE6DD8B,
    0x82A5FB52,
    0x8664E6E5,
    0xBE2B5B58,
    0xBAEA46EF,
    0xB7A96036,
    0xB3687D81,
    0xAD2F2D84,
    0xA9EE3033,
    0xA4AD16EA,
    0xA06C0B5D,
    0xD4326D90,
    0xD0F37027,
    0xDDB056FE,
    0xD9714B49,
    0xC7361B4C,
    0xC3F706FB,
    0xCEB42022,
    0xCA753D95,
    0xF23A8028,
    0xF6FB9D9F,
    0xFBB8BB46,
    0xFF79A6F1,
    0xE13EF6F4,
    0xE5FFEB43,
    0xE8BCCD9A,
    0xEC7DD02D,
    0x34867077,
    0x30476DC0,
    0x3D044B19,
    0x39C556AE,
    0x278206AB,
    0x23431B1C,
    0x2E003DC5,
    0x2AC12072,
    0x128E9DCF,
    0x164F8078,
    0x1B0CA6A1,
    0x1FCDBB16,
    0x018AEB13,
    0x054BF6A4,
    0x0808D07D,
    0x0CC9CDCA,
    0x7897AB07,
    0x7C56B6B0,
    0x71159069,
    0x75D48DDE,
    0x6B93DDDB,
    0x6F52C06C,
    0x6211E6B5,
    0x66D0FB02,
    0x5E9F46BF,
    0x5A5E5B08,
    0x571D7DD1,
    0x53DC6066,
    0x4D9B3063,
    0x495A2DD4,
    0x44190B0D,
    0x40D816BA,
    0xACA5C697,
    0xA864DB20,
    0xA527FDF9,
    0xA1E6E04E,
    0xBFA1B04B,
    0xBB60ADFC,
    0xB6238B25,
    0xB2E29692,
    0x8AAD2B2F,
    0x8E6C3698,
    0x832F1041,
    0x87EE0DF6,
    0x99A95DF3,
    0x9D684044,
    0x902B669D,
    0x94EA7B2A,
    0xE0B41DE7,
    0xE4750050,
    0xE9362689,
    0xEDF73B3E,
    0xF3B06B3B,
    0xF771768C,
    0xFA325055,
    0xFEF34DE2,
    0xC6BCF05F,
    0xC27DEDE8,
    0xCF3ECB31,
    0xCBFFD686,
    0xD5B88683,
    0xD1799B34,
    0xDC3ABDED,
    0xD8FBA05A,
    0x690CE0EE,
    0x6DCDFD59,
    0x608EDB80,
    0x644FC637,
    0x7A089632,
    0x7EC98B85,
    0x738AAD5C,
    0x774BB0EB,
    0x4F040D56,
    0x4BC510E1,
    0x46863638,
    0x42472B8F,
    0x5C007B8A,
    0x58C1663D,
    0x558240E4,
    0x51435D53,
    0x251D3B9E,
    0x21DC2629,
    0x2C9F00F0,
    0x285E1D47,
    0x36194D42,
    0x32D850F5,
    0x3F9B762C,
    0x3B5A6B9B,
    0x0315D626,
    0x07D4CB91,
    0x0A97ED48,
    0x0E56F0FF,
    0x1011A0FA,
    0x14D0BD4D,
    0x19939B94,
    0x1D528623,
    0xF12F560E,
    0xF5EE4BB9,
    0xF8AD6D60,
    0xFC6C70D7,
    0xE22B20D2,
    0xE6EA3D65,
    0xEBA91BBC,
    0xEF68060B,
    0xD727BBB6,
    0xD3E6A601,
    0xDEA580D8,
    0xDA649D6F,
    0xC423CD6A,
    0xC0E2D0DD,
    0xCDA1F604,
    0xC960EBB3,
    0xBD3E8D7E,
    0xB9FF90C9,
    0xB4BCB610,
    0xB07DABA7,
    0xAE3AFBA2,
    0xAAFBE615,
    0xA7B8C0CC,
    0xA379DD7B,
    0x9B3660C6,
    0x9FF77D71,
    0x92B45BA8,
    0x9675461F,
    0x8832161A,
    0x8CF30BAD,
    0x81B02D74,
    0x857130C3,
    0x5D8A9099,
    0x594B8D2E,
    0x5408ABF7,
    0x50C9B640,
    0x4E8EE645,
    0x4A4FFBF2,
    0x470CDD2B,
    0x43CDC09C,
    0x7B827D21,
    0x7F436096,
    0x7200464F,
    0x76C15BF8,
    0x68860BFD,
    0x6C47164A,
    0x61043093,
    0x65C52D24,
    0x119B4BE9,
    0x155A565E,
    0x18197087,
    0x1CD86D30,
    0x029F3D35,
    0x065E2082,
    0x0B1D065B,
    0x0FDC1BEC,
    0x3793A651,
    0x3352BBE6,
    0x3E119D3F,
    0x3AD08088,
    0x2497D08D,
    0x2056CD3A,
    0x2D15EBE3,
    0x29D4F654,
    0xC5A92679,
    0xC1683BCE,
    0xCC2B1D17,
    0xC8EA00A0,
    0xD6AD50A5,
    0xD26C4D12,
    0xDF2F6BCB,
    0xDBEE767C,
    0xE3A1CBC1,
    0xE760D676,
    0xEA23F0AF,
    0xEEE2ED18,
    0xF0A5BD1D,
    0xF464A0AA,
    0xF9278673,
    0xFDE69BC4,
    0x89B8FD09,
    0x8D79E0BE,
    0x803AC667,
    0x84FBDBD0,
    0x9ABC8BD5,
    0x9E7D9662,
    0x933EB0BB,
    0x97FFAD0C,
    0xAFB010B1,
    0xAB710D06,
    0xA6322BDF,
    0xA2F33668,
    0xBCB4666D,
    0xB8757BDA,
    0xB5365D03,
    0xB1F740B4,
]

UNSIGNED = lambda n: n & 0xFFFFFFFF


def memcrc(b):
    """Compute the CRC-32 of the bytes in b, starting with an initial crc of 0."""
    n = len(b)
    c = s = 0
    for ch in b:
        tabidx = (s >> 24) ^ ch
        s = UNSIGNED((s << 8)) ^ crctab[tabidx]

    while n:
        c = n & 0o377
        n = n >> 8
        s = UNSIGNED(s << 8) ^ crctab[(s >> 24) ^ c]
    return UNSIGNED(~s)


def calculate_crc(fname):
    """Calculate the CRC of a file."""
    try:
        buffer = open(fname, "rb").read()
        return f"{memcrc(buffer)}\t{len(buffer)}\t{fname}"
    except IOError:
        print("Unable to open input file", fname)
        exit(-1)
    except Exception as err:
        print("Error processing the file", err)
        exit(-1)


# protocol implementation

CLIENT_ID_LEN = 16
PUBLIC_KEY_SIZE = 160
AES_KEY_SIZE = 16
ENCRYPTED_AES_KEY_SIZE = 128
MAX_USER_NAME_LEN = 255
MAX_FILE_NAME_LEN = 255

REQUEST_MIN_LEN = 23
MAX_FILE_CONTENT_LENGTH = 0xFFFFFFFF
MAX_REQUEST_LENGTH = REQUEST_MIN_LEN + MAX_FILE_NAME_LEN + 4 + MAX_FILE_CONTENT_LENGTH


class RequestCode(Enum):
    """Request codes for the client to send to the server."""

    SIGN_UP = 1025
    SEND_PUBLIC_KEY = 1026
    SIGN_IN = 1027
    SEND_FILE = 1028
    CRC_VALID = 1029
    CRC_INVALID = 1030
    CRC_INVALID_4TH_TIME = 1031


class ResponseCode(Enum):
    """Response codes for the server to send to the client."""

    SUCCESS_RESTORE = 210
    SUCCESS_LIST = 211
    SUCCESS_SAVE = 212
    ERROR_NO_FILE = 1001
    ERROR_NO_CLIENT = 1002
    ERROR_GENERAL = 1003


# validations


def validate_range(
    var_name: str,
    number: int,
    uint_type: Literal["uint8_t", "uint16_t", "uint32_t", "uint64_t"],
) -> None:
    """Validate that a number is within the range of a given unsigned integer type."""
    ranges = {
        "uint8_t": (0, 0xFF),
        "uint16_t": (0, 0xFFFF),
        "uint32_t": (0, 0xFFFFFFFF),
        "uint64_t": (0, 0xFFFFFFFFFFFFFFFF),
    }

    min_val, max_val = ranges[uint_type]
    if not min_val <= number <= max_val:
        raise ValueError(f"{var_name} {number} is out of range for {uint_type}.")


def validate_request(req: RequestCode) -> None:
    """Validate that a request code is valid."""
    if req not in RequestCode:
        raise ValueError(f"Invalid reqeust code: {req.value}")


def validate_response(res: ResponseCode) -> None:
    """Validate that a response code is valid."""
    if res not in ResponseCode:
        raise ValueError(f"Invalid response code: {res.value}")


# common classes


class ClientID:
    """A class to represent a client ID."""

    def __init__(self, upper: int, lower: int):
        validate_range("upper", upper, "uint64_t")
        validate_range("lower", lower, "uint64_t")
        self.upper = upper
        self.lower = lower


class ClientName:
    """A class to represent a client name."""

    def __init__(self, name: str):
        validate_range("name_len", len(name), "uint8_t")
        self.validate_name(name)
        self.name_len = len(name)
        self.name = name

    @staticmethod
    def validate_name(name: str) -> None:
        """Validate that a name is valid."""
        # Check for directory traversal characters
        if ".." in name or "/" in name or "\\" in name:
            raise ValueError("Invalid characters in name")

        # Check for invalid characters
        valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
        if any(char not in valid_chars for char in name):
            raise ValueError("Invalid characters in name")


class Filename:
    """A class to represent a filename."""

    def __init__(self, filename: str):
        validate_range("name_len", len(filename), "uint16_t")
        self.validate_filename(filename)
        self.name_len = len(filename)
        self.filename = filename

    @staticmethod
    def validate_filename(filename: str) -> None:
        """Validate that a filename is valid."""
        # Check for directory traversal characters
        if ".." in filename or "/" in filename or "\\" in filename:
            raise ValueError("Invalid characters in filename")

        # Check for invalid characters
        valid_chars = f"-_.() {string.ascii_letters}{string.digits}"
        if any(char not in valid_chars for char in filename):
            raise ValueError("Invalid characters in filename")


class Payload:
    """A class to represent a payload."""

    def __init__(self, size: int, payload: bytes):
        validate_range("payload.size", size, "uint32_t")
        self.size = size
        self.payload = payload


# requests


# class _RequestBase(ABC):
#     def __init__(
#         self, client_id: ClientID, version: int, req: RequestCode, payload_size: int
#     ):
#         validate_range("version", version, "uint8_t")
#         validate_range("payload_size", payload_size, "uint32_t")
#         validate_request(req)

#         self.client_id = client_id
#         self.version = version
#         self.req = req.value
#         self.payload_size = payload_size

#     def pack(self) -> bytes:
#         """Pack the request into a byte string."""
#         return struct.pack(
#             "<Q Q B H I",
#             self.client_id.upper,
#             self.client_id.lower,
#             self.version,
#             self.req,
#             self.payload_size,
#         )


class RequestMessage:
    """A class to represent a request message."""

    def __init__(self, buffer: bytes):
        if len(buffer) < REQUEST_MIN_LEN:
            raise ValueError(
                f"Invalid request length {len(buffer)} < {REQUEST_MIN_LEN}"
            )
        self.client_id = buffer[:CLIENT_ID_LEN]
        buffer = buffer[CLIENT_ID_LEN:]
        header_remaining_len = 7
        self.version, self.code, self.payload_size = struct.unpack(
            "<BHI", buffer[:header_remaining_len]
        )
        buffer = buffer[header_remaining_len:]
        if len(buffer) != self.payload_size:
            raise ValueError(
                f"Invalid payload length {len(buffer)} != {self.payload_size}"
            )
        self.payload = buffer


# responses


class _ResponseBase(ABC):
    def __init__(self, version: int, res: ResponseCode):
        self.version = version
        self.res = res

    def __str__(self) -> str:
        return f"Version: {self.version}\nResponse Code: {self.res}"


Response = _ResponseBase


class ResponseErrorGeneral(_ResponseBase):
    """A response indicating a general error."""

    def __init__(self, version: int):
        super().__init__(version, ResponseCode.ERROR_GENERAL)


class ResponseErrorNoClient(_ResponseBase):
    """A response indicating that the client does not exist."""

    def __init__(self, version: int):
        super().__init__(version, ResponseCode.ERROR_NO_CLIENT)


class _ResponseWithFileName(_ResponseBase):
    def __init__(self, version: int, res: ResponseCode, filename: Filename):
        super().__init__(version, res)
        self.filename = filename

    def __str__(self) -> str:
        return f"""{super().__str__()}\n
        Name length: {self.filename.name_len}\n
        Filename: {self.filename.filename}"""


class ResponseSuccessSave(_ResponseWithFileName):
    """A response indicating that a file was saved successfully."""

    def __init__(self, version: int, filename: Filename):
        super().__init__(version, ResponseCode.SUCCESS_SAVE, filename)


class ResponseErrorNoFile(_ResponseWithFileName):
    """A response indicating that a file does not exist."""

    def __init__(self, version: int, filename: Filename):
        super().__init__(version, ResponseCode.ERROR_NO_FILE, filename)


class _ResponseWithFileNameAndPayload(_ResponseWithFileName):
    def __init__(
        self, version: int, res: ResponseCode, filename: Filename, payload: Payload
    ):
        super().__init__(version, res, filename)
        self.payload = payload

    def __str__(self) -> str:
        return f"{super().__str__()}\nPayload size: {self.payload.size}"


class ResponseSuccessRestore(_ResponseWithFileNameAndPayload):
    """A response indicating that a file was restored successfully."""

    def __init__(self, version: int, filename: Filename, payload: Payload):
        super().__init__(version, ResponseCode.SUCCESS_RESTORE, filename, payload)


class ResponseSuccessList(_ResponseWithFileNameAndPayload):
    """A response indicating that a list of files was retrieved successfully."""

    def __init__(self, version: int, filename: Filename, payload: Payload):
        super().__init__(version, ResponseCode.SUCCESS_LIST, filename, payload)

    def __str__(self) -> str:
        return (
            super().__str__() + f"\nFiles list:\n{self.payload.payload.decode('utf-8')}"
        )


# Database Management


class DatabaseManager:
    """A class to manage the database."""

    CLIENTS_TABLE = "clients"
    TEMP_FILE_PATH = "saved"
    FILES_TABLE = "files"

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._create_tables()

    def create_new_client(self, username: str) -> None:
        """Create a new client in the database."""
        self._validate_username(username)
        client_id = os.urandom(CLIENT_ID_LEN)
        cursor = self.conn.cursor()
        cursor.execute(
            f"INSERT INTO {self.CLIENTS_TABLE} (id, name, public_key, last_seen, aes_key) VALUES (?, ?, ?, ?, ?);",
            (client_id, username, bytes(0), time.asctime(), bytes(0)),
        )
        self.conn.commit()
        cursor.close()

    def get_client_by_name(self, username: str):
        """Get a client by their username."""
        self._validate_username(username)

        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT * FROM {self.CLIENTS_TABLE} WHERE name = ?;", (username,)
        )
        rows = cursor.fetchall()
        cursor.close()
        if not rows:
            return []
        return rows[0]

    def get_client_by_id(self, client_id):
        """Get a client by their ID."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"SELECT * FROM {self.CLIENTS_TABLE} WHERE id = ?;", (client_id,)
        )
        rows = cursor.fetchall()
        cursor.close()
        if not rows:
            return []
        return rows[0]

    def update_public_key(self, client_id, public_key):
        """Update a client's public key."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE {self.CLIENTS_TABLE} SET public_key = ? WHERE id = ?;",
            (public_key, client_id),
        )
        self.conn.commit()
        cursor.close()

    def update_aes_key(self, client_id, aes_key):
        """Update a client's AES key."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE {self.CLIENTS_TABLE} SET aes_key = ? WHERE id = ?;",
            (aes_key, client_id),
        )
        self.conn.commit()
        cursor.close()

    def insert_unvalidated_file(self, filename: str, file_content, file_id):
        """Insert a file into the database."""
        self._validate_filename(filename)

        if not os.path.exists(self.TEMP_FILE_PATH):
            os.mkdir(self.TEMP_FILE_PATH)
        file_path = self._id_to_path(file_id, filename)
        with open(file_path, "wb") as f:
            f.write(file_content)

        cursor = self.conn.cursor()
        cursor.execute(
            f"INSERT INTO {self.FILES_TABLE} (id, file_name, saved_path, verified) VALUES (?, ?, ?, ?);",
            (file_id, filename, file_path, 0),
        )
        self.conn.commit()
        cursor.close()

    def set_file_to_valid(self, file_id):
        """Set a file to be valid."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE {self.FILES_TABLE} SET verified = ? WHERE file_name = ?;",
            (1, file_id),
        )
        self.conn.commit()
        cursor.close()

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.CLIENTS_TABLE} (
                    id BLOB PRIMARY KEY,
                    name TEXT,
                    public_key BLOB,
                    last_seen TEXT,
                    aes_key BLOB
                )"""
        )
        cursor.execute(
            f"""CREATE TABLE IF NOT EXISTS {self.FILES_TABLE} (
                    id BLOB,
                    file_name TEXT,
                    saved_path TEXT,
                    verified INTEGER
                )"""
        )
        cursor.close()

    def _validate_username(self, username: str) -> None:
        for ch in username:
            if not ch.isalpha() and ch != " ":
                raise ValueError("Invalid username.")

    def _validate_filename(self, username: str) -> None:
        for ch in username:
            if not ch.isalnum() and ch != " " and ch != "." and ch != "/":
                raise ValueError("Invalid filename.")

    def _id_to_path(self, file_id, filename):
        return (
            self.TEMP_FILE_PATH
            + "/"
            + str(base64.b32encode(file_id), "utf-8")
            + SHA256.new(bytes(filename, "utf-8")).hexdigest()
            + ".tmp"
        )


class FileHandler:
    """A class to handle reading server and backup information from files."""

    SERVER_INFO_FILE = "server.info"
    BACKUP_INFO_FILE = "backup.info"

    def __init__(self):
        self.server_info_file = self.SERVER_INFO_FILE
        self.backup_info_file = self.BACKUP_INFO_FILE

    @staticmethod
    def validate_ip(ip: str) -> None:
        """Validate that an IP address is valid."""
        try:
            socket.inet_aton(ip)
        except socket.error as exc:
            raise ValueError("Invalid IP address.") from exc

    @staticmethod
    def validate_port(port: str) -> None:
        """Validate that a port number is valid."""
        if not 0 <= int(port) <= 65535:
            raise ValueError("Invalid port number.")

    def read_server_info(self) -> Tuple[str, int]:
        """Read the server information from the server.info file."""
        try:
            with open(self.server_info_file, mode="r", encoding="utf-8") as file:
                ip_address, port = file.readline().strip().split(":")
                self.validate_ip(ip_address)
                self.validate_port(port)
                port = int(port)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"{self.server_info_file} file not found.") from exc
        return ip_address, port

    def read_backup_info(self) -> List[str]:
        """Read the backup information from the backup.info file."""
        try:
            with open(self.backup_info_file, mode="r", encoding="utf-8") as file:
                filenames = [line.strip() for line in file]
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"{self.backup_info_file} file not found.") from exc
        if len(filenames) < 2:
            raise RuntimeError("At least two files are required to run the client.")
        return filenames


class UniqueIDGenerator:
    """A class to generate unique IDs."""

    def __init__(self):
        self.generated_ids = set()

    def generate_unique_id(self) -> int:
        """Generate a unique ID."""
        while True:
            unique_id = random.randint(0, 0xFFFFFFFF)
            if unique_id not in self.generated_ids:
                self.generated_ids.add(unique_id)
                return unique_id


class Client:
    """A class to represent a client."""

    def __init__(self, client_sock: socket.socket, user_db: DatabaseManager):
        self.sock = client_sock
        self.db = user_db
        self.last_active_time = time.time()
        self.client_id = bytes(16)
        self.awaiting_file = False
        self.active = True

    def handle_message(self):
        """Handle a message from the client."""
        if not self.active:
            raise RuntimeError(f"got message on inactive client {self.client_id}")

        self.last_active_time = time.time()
        try:
            buffer = self.sock.recv(MAX_REQUEST_LENGTH)
            request = RequestMessage(buffer)
            match request.code:
                case RequestCode.SIGN_UP:
                    self._handle_registration(request)
                case RequestCode.SEND_PUBLIC_KEY:
                    self._handle_public_key(request)
                case RequestCode.SIGN_IN:
                    self._handle_login(request)
                case RequestCode.SEND_FILE:
                    self._handle_file(request)
                case RequestCode.CRC_VALID:
                    self._handle_valid_crc(request)
                case RequestCode.CRC_INVALID:
                    self._handle_invalid_crc(request)
                case RequestCode.CRC_INVALID_4TH_TIME:
                    self._handle_terminate(request)
                case _:
                    raise ValueError(f"Invalid request code {request.code}")
        except Exception as e:
            print(
                f"failed to handle request with error: {str(e)}\nfrom client: {self.client_id}"
            )
            self._send_generic_failure()

    @staticmethod
    def _get_string_from_bytes(b: bytes) -> str:
        return str(b.split(bytes([ord("\0")]))[0], "utf-8")

    def _handle_registration(self, request):
        if self.awaiting_file:
            raise Exception("got registration message in file phase")
        if request.payload_size != MAX_USER_NAME_LEN:
            raise Exception("wrong payload size in registration")

        username = Client._get_string_from_bytes(request.payload)
        if self.db.get_client_by_name(username):
            return self._send_registration_failed()
        self.db.create_new_client(username)
        self.username = username
        self.client_id = self.db.get_client_by_name(username)[0]
        self._send_registration_successful()

    def _handle_public_key(self, request):
        if self.awaiting_file:
            raise Exception("got public key message in file phase")
        if request.payload_size != MAX_USER_NAME_LEN + PUBLIC_KEY_SIZE:
            raise Exception("wrong payload size in public key")

        username = Client._get_string_from_bytes(request.payload[:MAX_USER_NAME_LEN])
        public_key = request.payload[MAX_USER_NAME_LEN:]
        if self.client_id != request.client_id or self.username != username:
            raise Exception("client_id or username not matching")

        self.db.update_public_key(self.client_id, public_key)
        self._send_public_key_received(public_key)
        self.awaiting_file = True

    def _handle_login(self, request):
        if self.awaiting_file:
            raise Exception("got login message in file phase")
        if request.payload_size != MAX_USER_NAME_LEN:
            raise Exception("wrong payload size in login")
        client_row = self.db.get_client_by_id(request.client_id)
        if not client_row or not client_row[2]:
            return self._send_login_failed()
        username = Client._get_string_from_bytes(request.payload[:MAX_USER_NAME_LEN])
        if username != client_row[1]:
            raise Exception("client_id or username not matching")

        self.client_id = request.client_id
        self.username = username
        self._send_login_successful(client_row[2])
        self.awaiting_file = True

    def _handle_file(self, request):
        if not self.awaiting_file:
            raise Exception("got file message in login phase")
        if self.client_id != request.client_id:
            raise Exception("client_id not matching")
        if request.payload_size <= 4 + MAX_FILE_NAME_LEN:
            raise Exception("file message has no file content")
        (content_size,) = struct.unpack("<I", request.payload[:4])
        padded_content_size = (content_size // AES_KEY_SIZE) * AES_KEY_SIZE
        if content_size % AES_KEY_SIZE != 0:
            padded_content_size += AES_KEY_SIZE
        self.filename = Client._get_string_from_bytes(
            request.payload[4 : MAX_FILE_NAME_LEN + 4]
        )
        encrypted_file = request.payload[
            MAX_FILE_NAME_LEN + 4 : MAX_FILE_NAME_LEN + 4 + padded_content_size
        ]
        file_crc = self._decrypt_and_save_file(encrypted_file, content_size)
        self._send_file_received(content_size, file_crc)
        self.awaiting_file = False

    def _handle_valid_crc(self, request):
        if self.awaiting_file:
            raise Exception("got valid crc message while waiting for file")
        if self.client_id != request.client_id:
            raise Exception("client_id not matching")
        if request.payload_size != MAX_FILE_NAME_LEN:
            raise Exception("wrong payload size in valid crc")
        filename = Client._get_string_from_bytes(request.payload)
        if filename != self.filename:
            raise Exception("filename not matching")
        self.db.set_file_to_valid(self.client_id)
        self._send_generic_ack()

    def _handle_invalid_crc(self, request):
        if self.client_id != request.client_id:
            raise Exception("client_id not matching")
        if request.payload_size != MAX_FILE_NAME_LEN:
            raise Exception("wrong payload size in invalid crc")
        filename = Client._get_string_from_bytes(request.payload)
        if filename != self.filename:
            raise Exception("filename not matching")
        self.awaiting_file = True

    def _handle_terminate(self, request):
        if not self.awaiting_file:
            raise Exception("got terminate message in login phase")
        if self.client_id != request.client_id:
            raise Exception("client_id not matching")
        if request.payload_size != MAX_FILE_NAME_LEN:
            raise Exception("wrong payload size in terminate")
        filename = Client._get_string_from_bytes(request.payload)
        if filename != self.filename:
            raise Exception("filename not matching")
        self._send_generic_ack()
        self.active = False

    def _send_registration_successful(self):
        response = responses.RegistrationSuccessful(self.client_id)
        self.sock.send(response.serialize())

    def _send_registration_failed(self):
        response = responses.RegistrationFailed()
        self.sock.send(response.serialize())

    def _send_public_key_received(self, public_key):
        enc_aes_key = self._get_encrypted_aes_key(public_key)
        response = responses.PublicKeyReceived(self.client_id, enc_aes_key)
        self.sock.send(response.serialize())

    def _send_file_received(self, content_size, file_crc):
        response = responses.FileReceived(
            self.client_id, content_size, self.filename, file_crc
        )
        self.sock.send(response.serialize())

    def _send_generic_ack(self):
        response = responses.GenericAck(self.client_id)
        self.sock.send(response.serialize())

    def _send_login_successful(self, public_key):
        enc_aes_key = self._get_encrypted_aes_key(public_key)
        response = responses.LoginSuccessful(self.client_id, enc_aes_key)
        self.sock.send(response.serialize())

    def _send_login_failed(self):
        response = responses.LoginFailed(self.client_id)
        self.sock.send(response.serialize())

    def _send_generic_failure(self):
        response = responses.GenericFailure()
        self.sock.send(response.serialize())

    def _get_encrypted_aes_key(self, public_key):
        self.aes_key = urandom(AES_KEY_SIZE)
        self.db.update_aes_key(self.client_id, self.aes_key)

        rsa_key = RSA.import_key(public_key)
        rsa = PKCS1_OAEP.new(rsa_key)
        return rsa.encrypt(self.aes_key)

    def _decrypt_and_save_file(self, encrypted_file, content_size):
        file_content = bytes()
        for i in range(len(encrypted_file) // AES_KEY_SIZE):
            aes = AES.new(self.aes_key, mode=AES.MODE_CBC, IV=bytes(16))
            file_content += aes.decrypt(
                encrypted_file[i * AES_KEY_SIZE : (i + 1) * AES_KEY_SIZE]
            )
        if len(file_content) < content_size:
            raise Exception("something went wrong decrypting the file")
        file_content = file_content[:content_size]
        self.db.insert_unvalidated_file(self.filename, file_content, self.client_id)
        return memcrc(file_content)


class RequestGenerator:
    """A class to generate requests for the client."""

    def __init__(self, client_id: ClientID):
        self.client_id = client_id

    # def generate_save_request(self, filename: str) -> Request:
    #     """Generate a request to save a file."""
    #     with open(filename, "rb") as f:
    #         content = f.read()
    #     return RequestSave(self.client_id, VERSION, filename, content)

    # def generate_restore_request(self, filename: str) -> Request:
    #     """Generate a request to restore a file."""
    #     return RequestRestore(self.client_id, VERSION, filename)


def main():
    """The main function of the client."""
    # unique_id_generator = UniqueIDGenerator()
    # unique_id = unique_id_generator.generate_unique_id()  # step 1

    # reader = FileHandler()
    # ip_address, port = reader.read_server_info()  # step 2
    # # filenames = reader.read_backup_info()  # step 3

    # client = Client(ip_address, port)

    # generator = RequestGenerator(unique_id)
    # client.send_request(generator.generate_list_request())  # step 4


if __name__ == "__main__":
    main()
