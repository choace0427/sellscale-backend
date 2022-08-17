import argparse
from typing import Union
from cryptography.fernet import Fernet
import os

# Env Var
_ENCRYPTION_KEY_ENV_VAR = 'ENCRYPTION_KEY'

# Commands
_ENCRYPT = 'encrypt'
_DECRYPT = 'decrypt'


def _get_key() -> str:
    return os.environ[_ENCRYPTION_KEY_ENV_VAR]


class CryptoBox:
    def __init__(self):
        self._fernet = Fernet(_get_key())

    def encrypt_to_bytes(self, plaintext: Union[str, bytes]) -> bytes:
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()

        return self._fernet.encrypt(plaintext)

    def encrypt_to_file(self, plaintext: Union[str, bytes], filepath: str) -> bytes:
        os.makedirs(name=os.path.dirname(filepath), exist_ok=True)
        outfile = open(filepath, 'wb+')
        outfile.write(self.encrypt_to_bytes(plaintext))

    def decrypt_from_bytes(
        self, ciphertext: bytes, as_bytes: bool = False
    ) -> Union[str, bytes]:
        decrypted = self._fernet.decrypt(ciphertext)
        if not as_bytes:
            decrypted = decrypted.decode()

        return decrypted

    def decrypt_from_file(self, filepath: str, **kwargs) -> Union[str, bytes]:
        f = open(filepath, 'rb')
        ciphertext = f.read()
        f.close()
        # Need to strip away any spaces added by linters
        ciphertext = ciphertext.strip()
        return self.decrypt_from_bytes(ciphertext, **kwargs)


parser = argparse.ArgumentParser()
parser.add_argument('--mode', choices=[_ENCRYPT, _DECRYPT], required=True)
inputs = parser.add_mutually_exclusive_group(required=True)
inputs.add_argument('--input-file', help='Path to input file')
inputs.add_argument('--input', help='Raw input text')

parser.add_argument('--output-file', help='Path to output file')


def _get_input(parsed_args: argparse.Namespace):
    return (
        parsed_args.input
        or open(
            parsed_args.input_file, 'r' if parsed_args.mode == _ENCRYPT else 'rb'
        ).read()
    )


if __name__ == '__main__':
    args = parser.parse_args()

    text = _get_input(args)

    if args.mode == _ENCRYPT:
        output = CryptoBox().encrypt_to_bytes(text)
    elif args.mode == _DECRYPT:
        output = CryptoBox().decrypt_from_bytes(text)

    if args.output_file:
        os.makedirs(name=os.path.dirname(args.output_file), exist_ok=True)
        outfile = open(args.output_file, 'wb+' if (args.mode == _ENCRYPT) else 'w+')
        outfile.write(output)
    else:
        print(output)
