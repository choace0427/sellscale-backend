def get_unique_int(x: int, y: int) -> int:
    return ((x + y) * (x + y + 1)) / 2 + min(x, y) - 1000000000
