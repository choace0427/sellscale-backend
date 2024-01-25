from ....utils.abstract.attr_utils import deep_get


def get_current_location(data):
    # ______ is based in ______

    first_name = deep_get(data, "personal.first_name")
    last_name = deep_get(data, "personal.last_name")
    print(first_name, last_name)
    if not first_name or not last_name:  # No name
        return {"response": ""}
    name = first_name + " " + last_name

    location = deep_get(data, "personal.location.default")
    print(location)
    if not location:  # No location
        return {"response": ""}

    return {"response": f"{name} is based in {location}"}
