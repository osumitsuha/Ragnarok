import random
import string


def rag_round(value: float, decimals: int) -> float:
    tolerance = 10 ** decimals

    return int(value * tolerance + 0.5) / tolerance


def random_string(len: int) -> str:
    return "".join(
        random.choice(string.ascii_lowercase + string.digits) for _ in range(len)
    )
