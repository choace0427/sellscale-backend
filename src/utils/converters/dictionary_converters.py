def dictionary_normalization(keys: set, dictionaries: list[dict]) -> bool:
    """In place normalization of dictionaries to have the same keys

    Args:
        keys (set): The keys to normalize to
        dictionaries (list[dict]): The dictionaries to normalize

    Returns:
        bool: True if the normalization was successful, False otherwise
    """
    for dictionary in dictionaries:

        # Dictionary keys must be subset of keys
        if not keys.issuperset(dictionary.keys()):
            raise ValueError("Dictionary keys do not match")

        for key in keys:
            if key not in dictionary:
                dictionary[key] = None

    return True

