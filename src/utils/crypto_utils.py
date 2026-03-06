from dataclasses import dataclass
from typing import ByteString

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


@dataclass
class AesEcbEncryptor:
    key: bytes

    def encrypt_base64(self, data: ByteString) -> str:
        import base64

        cipher = AES.new(self.key, AES.MODE_ECB)
        encrypted = cipher.encrypt(pad(bytes(data), AES.block_size))
        return base64.b64encode(encrypted).decode()


@dataclass
class AesCbcEncryptor:
    key: bytes
    iv: bytes

    def encrypt_hex(self, data: ByteString) -> str:
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        encrypted = cipher.encrypt(pad(bytes(data), AES.block_size))
        return encrypted.hex()
