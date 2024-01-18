import re
from typing import Any, Dict, List, NewType, Optional, Union

PathSpec = NewType("PathSpec", List[Union[str, int]])


def str_path_to_path_steps(path: str, *delimiters: str) -> PathSpec:
    steps = re.split("|".join(map(re.escape, delimiters)), path)
    for step in steps:
        if step.isdigit():
            yield int(step)
        else:
            yield step


def deep_set(obj: dict, path: PathSpec, value: Any):
    if isinstance(path, str):
        path = str_path_to_path_steps(path, ".")

    path = list(path)
    for i, key in enumerate(path[:-1]):
        if isinstance(obj):
            obj = getattr(obj, key)
        elif isinstance(obj, dict):
            if key not in obj:
                obj[key] = {}
            obj = obj[key]
        else:
            raise ValueError("{} is not a dictionary.".format(".".join(path[: i + 1])))

    final_path = path[-1]
    if isinstance(obj, (list, dict)):
        obj[final_path] = value
    else:
        raise ValueError(f"Can not set {final_path} of {obj}")


def deep_get(obj: Union[List, Dict], path: str, default=None) -> Optional[Any]:
    steps = str_path_to_path_steps(path, ".")

    for step in steps:
        if not obj:
            return default

        if isinstance(obj, dict):
            obj = obj.get(step, None)
        elif isinstance(obj, list) and str(step).isnumeric():
            next_index = int(step)
            if next_index >= len(obj):
                return default
            obj = obj[next_index]
        else:
            try:
                obj = getattr(obj, step)
            except:
                return default

    return obj


def compare_objs_deep(o1: Any, o2: Any, paths: List[str]):
    return all(deep_get(o1, path) == deep_get(o2, path) for path in paths)
