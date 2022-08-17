import os.path
import pickle
from typing import Callable


def cache_between_runs(key, override=False):
    filename = f'/tmp/{key}.pkl'

    def wrapper(f: Callable):
        def wrapped(*f_args, **f_kwargs):
            if not override and os.path.exists(filename):
                print(f'WARN: Using cached value: {filename}')
                return pickle.load(open(filename, 'rb'))

            result = f(*f_args, **f_kwargs)
            print(f'Stashing result of {f.__qualname__} to {filename}')
            pickle.dump(result, open(filename, 'wb+'))
            return result

        return wrapped

    return wrapper
