def has_consecutive_uppercase_string(st, num_consecutive):
    """
    Returns True if s contains a consecutive substring of length >= num_consecutive that is all uppercase.
    Otherwise, returns False.
    """
    consecutive_uppercase_count = 0
    consecutive_string = ""

    longest_consecutive_string = ""
    longest_consecutive_uppercase_count = 0
    for i in range(len(st)):
        if st[i].isupper() or st[i].isspace():
            if st[i].isupper():
                consecutive_uppercase_count += 1
                consecutive_string = consecutive_string + st[i]
                if longest_consecutive_uppercase_count < consecutive_uppercase_count:
                    longest_consecutive_uppercase_count = consecutive_uppercase_count
                    longest_consecutive_string = consecutive_string
            elif consecutive_uppercase_count > 0:
                consecutive_string = consecutive_string + st[i]
        else:
            consecutive_uppercase_count = 0
            consecutive_string = ""

    if longest_consecutive_uppercase_count >= num_consecutive:
        return True, longest_consecutive_string
    return False, None
