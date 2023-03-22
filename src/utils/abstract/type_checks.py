def is_number(potential_number):
    try:
        float(potential_number)
        return True
    except:
        return False
