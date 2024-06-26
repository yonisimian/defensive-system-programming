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

from typing import Literal
from enum import Enum
import selectors
import sqlite3
import socket
import struct
import base64
import time
import os
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Hash import SHA256

VERSION = 3
DEFAULT_PORT = 1256
PORT_FILE = "port.info"


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


def unsigned(n):
    """Return the unsigned value of n."""
    return n & 0xFFFFFFFF


def memcrc(b):
    """Compute the CRC-32 of the bytes in b, starting with an initial crc of 0."""
    n = len(b)
    c = s = 0
    for ch in b:
        tabidx = (s >> 24) ^ ch
        s = unsigned((s << 8)) ^ crctab[tabidx]

    while n:
        c = n & 0o377
        n = n >> 8
        s = unsigned(s << 8) ^ crctab[(s >> 24) ^ c]
    return unsigned(~s)


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

    SIGN_UP_SUCCEEDED = 1600
    SIGN_UP_FAILED = 1601
    PUBLIC_KEY_RECEIVED = 1602
    CRC_VALID = 1603
    MESSAGE_RECEIVED = 1604
    SIGN_IN_ALLOWED = 1605
    SIGN_IN_REJECTED = 1606
    GENERAL_ERROR = 1607


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


def validate_request_code(code: RequestCode) -> None:
    """Validate that a request code is valid."""
    if code not in RequestCode:
        raise ValueError(f"Invalid reqeust code: {code.value}")


def validate_response_code(code: ResponseCode) -> None:
    """Validate that a response code is valid."""
    if code not in ResponseCode:
        raise ValueError(f"Invalid response code: {code.value}")


class Request:
    """A class to represent a request from the client to the server"""

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
        self.code = RequestCode(self.code)
        validate_request_code(self.code)
        validate_range("payload_size", self.payload_size, "uint32_t")
        validate_range("version", self.version, "uint8_t")
        buffer = buffer[header_remaining_len:]
        if len(buffer) != self.payload_size:
            raise ValueError(
                f"Invalid payload length {len(buffer)} != {self.payload_size}"
            )
        self.payload = buffer


class Response:
    """Base class for all responses"""

    def __init__(self, code: ResponseCode, payload_size: int):
        self.version = VERSION
        self.code = code
        self.payload_size = payload_size

        validate_response_code(self.code)
        validate_range("payload_size", self.payload_size, "uint32_t")

    def pack(self) -> bytes:
        """pack the response into bytes"""
        return struct.pack("<BHI", self.version, self.code.value, self.payload_size)


class ResponseSignUpSuccess(Response):
    """Response of ResponseCode.SIGN_UP_SUCCEEDED"""

    def __init__(self, client_id: bytes):
        super().__init__(ResponseCode.SIGN_UP_SUCCEEDED, CLIENT_ID_LEN)
        if len(client_id) != CLIENT_ID_LEN:
            raise ValueError(
                f"Invalid client_id length {len(client_id)} != {CLIENT_ID_LEN}"
            )
        self.client_id = client_id

    def pack(self) -> bytes:
        return super().pack() + self.client_id


class ResponseSignUpFailed(Response):
    """Response of ResponseCode.SIGN_UP_FAILED"""

    def __init__(self):
        super().__init__(ResponseCode.SIGN_UP_FAILED, 0)


class ResponsePublicKeyReceived(Response):
    """Response of ResponseCode.PUBLIC_KEY_RECEIVED"""

    def __init__(self, client_id: bytes, encrypted_aes_key: bytes):
        super().__init__(
            ResponseCode.PUBLIC_KEY_RECEIVED, CLIENT_ID_LEN + ENCRYPTED_AES_KEY_SIZE
        )
        if len(client_id) != CLIENT_ID_LEN:
            raise ValueError(
                f"Invalid client_id length {len(client_id)} != {CLIENT_ID_LEN}"
            )
        if len(encrypted_aes_key) != ENCRYPTED_AES_KEY_SIZE:
            raise ValueError(
                f"Invalid enc_aes_key length {len(encrypted_aes_key)} != {ENCRYPTED_AES_KEY_SIZE}"
            )
        self.client_id = client_id
        self.key = encrypted_aes_key

    def pack(self) -> bytes:
        return super().pack() + self.client_id + self.key


class ResponseCRCValid(Response):
    """Response of ResponseCode.CRC_VALID"""

    def __init__(self, client_id: bytes, content_size: int, filename: str, crc: int):
        super().__init__(
            ResponseCode.CRC_VALID, CLIENT_ID_LEN + 4 + MAX_FILE_NAME_LEN + 4
        )
        if len(client_id) != CLIENT_ID_LEN:
            raise ValueError("Invalid client id len")
        if len(filename) > MAX_FILE_NAME_LEN:
            raise ValueError("Invalid file name len")
        self.client_id = client_id
        self.content_size = content_size
        self.filename = bytes(filename, "utf-8")
        self.crc = crc

    def pack(self) -> bytes:
        return (
            super().pack()
            + self.client_id
            + struct.pack("<I", self.content_size)
            + self.filename
            + b"\0" * (MAX_FILE_NAME_LEN - len(self.filename))
            + struct.pack("<I", self.crc)
        )


class ResponseMessageReceived(Response):
    """Response of ResponseCode.MESSAGE_RECEIVED"""

    def __init__(self, client_id: bytes):
        super().__init__(ResponseCode.MESSAGE_RECEIVED, CLIENT_ID_LEN)
        if len(client_id) != CLIENT_ID_LEN:
            raise ValueError("Invalid client id len")
        self.client_id = client_id

    def pack(self) -> bytes:
        return super().pack() + self.client_id


class ResponseSignInAllowed(Response):
    """Response of ResponseCode.SIGN_IN_ALLOWED"""

    def __init__(self, client_id: bytes, encrypted_aes_key: bytes):
        super().__init__(
            ResponseCode.SIGN_IN_ALLOWED, CLIENT_ID_LEN + ENCRYPTED_AES_KEY_SIZE
        )
        if len(client_id) != CLIENT_ID_LEN:
            raise ValueError("Invalid client id len")
        if len(encrypted_aes_key) != ENCRYPTED_AES_KEY_SIZE:
            raise ValueError("Invalid aes key len")
        self.client_id = client_id
        self.key = encrypted_aes_key

    def pack(self) -> bytes:
        return super().pack() + self.client_id + self.key


class ResponseSignInRejected(Response):
    """Response of ResponseCode.SIGN_IN_REJECTED"""

    def __init__(self, client_id: bytes):
        super().__init__(ResponseCode.SIGN_IN_REJECTED, CLIENT_ID_LEN)
        if len(client_id) != CLIENT_ID_LEN:
            raise ValueError("Invalid filename len")
        self.client_id = client_id

    def pack(self) -> bytes:
        return super().pack() + self.client_id


class ResponseGeneralError(Response):
    """Response of ResponseCode.GENERAL_ERROR"""

    def __init__(self):
        super().__init__(ResponseCode.GENERAL_ERROR, 0)


# Database Management


class DatabaseManager:
    """A class to manage the database."""

    DB_FILE_NAME = "server.db"
    CLIENTS_TABLE = "clients"
    TEMP_FILE_PATH = "saved"
    FILES_TABLE = "files"

    def __init__(self):
        self.conn = sqlite3.connect(self.DB_FILE_NAME)
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
            f"INSERT INTO {self.FILES_TABLE} (id, filename, saved_path, verified) VALUES (?, ?, ?, ?);",
            (file_id, filename, file_path, 0),
        )
        self.conn.commit()
        cursor.close()

    def set_file_to_valid(self, file_id):
        """Set a file to be valid."""
        cursor = self.conn.cursor()
        cursor.execute(
            f"UPDATE {self.FILES_TABLE} SET verified = ? WHERE filename = ?;",
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
                    filename TEXT,
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

# Server implementation

class ClientHandler:
    """A class to handle a client."""

    def __init__(self, client_sock: socket.socket, user_db: DatabaseManager):
        self.sock = client_sock
        self.db = user_db
        self.last_active_time = time.time()
        self.client_id = bytes(CLIENT_ID_LEN)
        self.aes_key = bytes(AES_KEY_SIZE)
        self.username = ""
        self.filename = ""
        self.awaiting_file = False
        self.active = True

    def handle_message(self):
        """Handle a message from the client."""
        if not self.active:
            raise RuntimeError(f"got message on inactive client {self.client_id}")

        self.last_active_time = time.time()
        try:
            buffer = self.sock.recv(MAX_REQUEST_LENGTH)
            request = Request(buffer)
            match request.code:
                case RequestCode.SIGN_UP:
                    self._sign_up(request)
                case RequestCode.SEND_PUBLIC_KEY:
                    self._send_public_key(request)
                case RequestCode.SIGN_IN:
                    self._sign_in(request)
                case RequestCode.SEND_FILE:
                    self._send_file(request)
                case RequestCode.CRC_VALID:
                    self._handle_valid_crc(request)
                case RequestCode.CRC_INVALID:
                    self._handle_invalid_crc(request)
                case RequestCode.CRC_INVALID_4TH_TIME:
                    self._handle_invalid_crc_4th_time(request)
                case _:
                    raise ValueError(f"Invalid request code {request.code}")
        except RuntimeError as e:
            print(
                f"failed to handle request with error: {str(e)}\nfrom client: {self.client_id}"
            )
            self.sock.send(ResponseGeneralError().pack())

    @staticmethod
    def _bytes_to_string(b: bytes) -> str:
        return str(b.split(bytes([ord("\0")]))[0], "utf-8")

    def _sign_up(self, request: Request):
        if self.awaiting_file:
            raise RuntimeError("got registration message in file phase")
        if request.payload_size != MAX_USER_NAME_LEN:
            raise RuntimeError("wrong payload size in registration")

        username = ClientHandler._bytes_to_string(request.payload)
        if self.db.get_client_by_name(username):
            self.sock.send(ResponseSignUpFailed().pack())
            return
        self.db.create_new_client(username)
        self.client_id = self.db.get_client_by_name(username)[0]
        self.sock.send(ResponseSignUpSuccess(self.client_id).pack())

    def _send_public_key(self, request: Request):
        if self.awaiting_file:
            raise RuntimeError("got public key message in file phase")
        if request.payload_size != MAX_USER_NAME_LEN + PUBLIC_KEY_SIZE:
            raise RuntimeError("wrong payload size in public key")

        username = ClientHandler._bytes_to_string(request.payload[:MAX_USER_NAME_LEN])
        public_key = request.payload[MAX_USER_NAME_LEN:]
        if self.client_id != request.client_id or self.username != username:
            raise RuntimeError("client_id or username not matching")

        self.db.update_public_key(self.client_id, public_key)
        enc_aes_key = self._get_encrypted_aes_key(public_key)
        self.sock.send(ResponsePublicKeyReceived(self.client_id, enc_aes_key).pack())
        self.awaiting_file = True

    def _sign_in(self, request: Request):
        if self.awaiting_file:
            raise RuntimeError("got login message in file phase")
        if request.payload_size != MAX_USER_NAME_LEN:
            raise RuntimeError("wrong payload size in login")
        client_row = self.db.get_client_by_id(request.client_id)
        if not client_row or not client_row[2]:
            self.sock.send(ResponseSignInRejected(request.client_id).pack())
            return
        username = ClientHandler._bytes_to_string(request.payload[:MAX_USER_NAME_LEN])
        if username != client_row[1]:
            raise RuntimeError("client_id or username not matching")

        self.client_id = request.client_id
        self.username = username
        enc_aes_key = self._get_encrypted_aes_key(client_row[2])
        self.sock.send(ResponseSignInAllowed(self.client_id, enc_aes_key).pack())
        self.awaiting_file = True

    def _send_file(self, request: Request):
        if not self.awaiting_file:
            raise RuntimeError("Received file request in login phase")
        if self.client_id != request.client_id:
            raise RuntimeError("Invalid client_id")
        if request.payload_size <= 4 + MAX_FILE_NAME_LEN:
            raise RuntimeError("Invalid (empty) file content")
        (content_size,) = struct.unpack("<I", request.payload[:4])
        padded_content_size = (content_size // AES_KEY_SIZE) * AES_KEY_SIZE
        if content_size % AES_KEY_SIZE != 0:
            padded_content_size += AES_KEY_SIZE
        filename = ClientHandler._bytes_to_string(
            request.payload[4 : MAX_FILE_NAME_LEN + 4]
        )
        encrypted_file = request.payload[
            MAX_FILE_NAME_LEN + 4 : MAX_FILE_NAME_LEN + 4 + padded_content_size
        ]
        file_crc = self._decrypt_and_save_file(encrypted_file, content_size)
        self.sock.send(
            ResponseCRCValid(self.client_id, content_size, filename, file_crc).pack()
        )
        self.awaiting_file = False

    def _handle_valid_crc(self, request: Request):
        if self.awaiting_file:
            raise RuntimeError("Received valid crc request while waiting for file")
        if self.client_id != request.client_id:
            raise RuntimeError("Invalid client_id")
        if request.payload_size != MAX_FILE_NAME_LEN:
            raise RuntimeError("Invalid payload size")
        filename = ClientHandler._bytes_to_string(request.payload)
        if filename != self.filename:
            raise RuntimeError("Invalid filename")
        self.db.set_file_to_valid(self.client_id)
        self.sock.send(ResponseMessageReceived(self.client_id).pack())

    def _handle_invalid_crc(self, request: Request):
        if self.client_id != request.client_id:
            raise RuntimeError("Invalid client_id")
        if request.payload_size != MAX_FILE_NAME_LEN:
            raise RuntimeError("Invalid payload size")
        filename = ClientHandler._bytes_to_string(request.payload)
        if filename != self.filename:
            raise RuntimeError("Invalid filename")
        self.awaiting_file = True

    def _handle_invalid_crc_4th_time(self, request: Request):
        if not self.awaiting_file:
            raise RuntimeError("Received terminate request in login phase")
        if self.client_id != request.client_id:
            raise RuntimeError("Invalid client_id")
        if request.payload_size != MAX_FILE_NAME_LEN:
            raise RuntimeError("Invalid payload size")
        filename = ClientHandler._bytes_to_string(request.payload)
        if filename != self.filename:
            raise RuntimeError("Invalid filename")
        self.sock.send(ResponseMessageReceived(self.client_id).pack())
        self.active = False

    def _get_encrypted_aes_key(self, public_key):
        self.aes_key = os.urandom(AES_KEY_SIZE)
        self.db.update_aes_key(self.client_id, self.aes_key)

        rsa_key = RSA.import_key(public_key)
        rsa = PKCS1_OAEP.new(rsa_key)
        return rsa.encrypt(self.aes_key)

    def _decrypt_and_save_file(self, encrypted_file, content_size):
        file_content = bytes()
        for i in range(len(encrypted_file) // AES_KEY_SIZE):
            aes = AES.new(self.aes_key, mode=AES.MODE_CBC, IV=bytes(AES_KEY_SIZE))
            file_content += aes.decrypt(
                encrypted_file[i * AES_KEY_SIZE : (i + 1) * AES_KEY_SIZE]
            )
        if len(file_content) < content_size:
            raise RuntimeError("File decryption failed")
        file_content = file_content[:content_size]
        self.db.insert_unvalidated_file(self.filename, file_content, self.client_id)
        return memcrc(file_content)


class Server:
    """A server class with two public functions: run and stop."""

    MAX_CONNECTIONS = 100

    def __init__(self, host: str) -> None:
        self.port = Server._read_port()
        self.host = host
        self.sel = selectors.DefaultSelector()
        self.not_stopped = True
        self.version = VERSION
        self.db = DatabaseManager()
        self.sock = None

    @staticmethod
    def _read_port() -> int:
        """Read the port from a file."""
        try:
            with open(PORT_FILE, mode="r", encoding="utf-8") as port_info:
                return int(port_info.read())
        except (FileNotFoundError, ValueError):
            return DEFAULT_PORT

    def _start(self, sock: socket.socket) -> None:
        """Start the server."""
        conn, _ = sock.accept()
        conn.setblocking(False)
        client = ClientHandler(conn, self.db)
        self.sel.register(conn, selectors.EVENT_READ, client.handle_message)

    def _create_socket(self) -> None:
        """Create the server socket."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.bind((self.host, self.port))
        self.sock.listen(Server.MAX_CONNECTIONS)
        self.sock.setblocking(False)
        self.sel.register(self.sock, selectors.EVENT_READ, self._start)

    def run(self) -> None:
        """Run the server."""
        self._create_socket()
        while self.not_stopped:
            events = self.sel.select()
            for key, _ in events:
                key.data(key.fileobj)

    def stop(self) -> None:
        """Stop the server."""
        self.not_stopped = False
        self.sel.close()
        if self.sock is not None:
            self.sock.close()


def main():
    """The main function of the client."""
    server = Server("localhost")
    server.run()


if __name__ == "__main__":
    main()
