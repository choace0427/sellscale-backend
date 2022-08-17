from time import sleep

from tqdm import tqdm


def sleep_with_progress(duration: float, increment: float = 0.1):
    for _ in tqdm(range(int(duration / increment))):
        sleep(increment)
