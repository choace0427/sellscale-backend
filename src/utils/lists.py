
def chunk_list(input_list, chunk_size):
    """Chunk a list into groups of a specified size."""
    return [input_list[i:i + chunk_size] for i in range(0, len(input_list), chunk_size)]

