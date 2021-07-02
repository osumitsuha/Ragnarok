def rag_round(value: float, decimals: int) -> float:
    tolerance = 10 ** decimals

    return int(value * tolerance + .5) / tolerance