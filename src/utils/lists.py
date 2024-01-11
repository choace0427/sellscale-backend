def chunk_list(input_list, chunk_size):
    """Chunk a list into groups of a specified size."""
    return [
        input_list[i : i + chunk_size] for i in range(0, len(input_list), chunk_size)
    ]


def format_str_join(items, ending_word="or"):
    if len(items) > 1:
        return ", ".join(items[:-1]) + f", {ending_word} " + items[-1]
    elif items:
        return items[0]
    else:
        return ""
