import hashlib


def get_unique_int(x: int, y: int) -> int:
    # Generate a unique randomized int from two int without collisions under 2^25
    return int.from_bytes(hashlib.sha256(f"{x}{y}".encode("utf-8")).digest(), "big") % (
        2**25
    )
