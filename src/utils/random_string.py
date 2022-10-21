import os.path
import random
import secrets
import string


def generate_secure_random_hex(num_chars: int):
    return secrets.token_hex(int(num_chars / 2))


def generate_random_alphabet(num_chars: int):
    return "".join([random.choice(string.ascii_letters) for _ in range(num_chars)])


def generate_random_alphanumeric(num_chars: int):
    return "".join(
        map(
            lambda _: random.choice(string.ascii_letters + string.digits),
            range(num_chars),
        )
    )


def generate_random_file_path() -> str:
    file_path = [generate_secure_random_hex(i) for i in range(4, 6)]
    file_path.append("file.txt")
    file_path.insert(0, "test")
    file_path = os.path.join(*file_path)
    return file_path
