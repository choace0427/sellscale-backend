import hashlib
import uuid

def generate_uuid(base: str = "", salt: str = "") -> str:
    # Convert number to string and salt and convert to bytes
    bites = (str(base) + str(salt)).encode()

    # Convert string to bytes and hash using SHA256 algorithm
    hashed_bytes = hashlib.md5(bites).digest()

    # Use hashed bytes to create a UUID
    uuid_val = uuid.UUID(bytes=hashed_bytes, version=5)

    # Convert UUID to string
    uuid_str = str(uuid_val)

    return uuid_str