from objects import glob
from constants.playmode import Mode
from utils import log

def calculate_accuracy(mode, count_300, count_100, count_50, count_geki, count_katu, count_miss):
    if mode == Mode.OSU:
        if glob.debug:
            log.debug("Calculating accuracy for standard")

        acc = (50 * count_50 + 100 * count_100 + 300 * count_300) / (300 * (count_miss + count_50 + count_100 + count_300))

    if mode == Mode.TAIKO:
        if glob.debug:
            log.debug("Calculating accuracy for taiko")

        acc = (0.5 * count_100 + count_300) / (
            count_miss + count_100 + count_300
        )

    if mode == Mode.CATCH:
        if glob.debug:
            log.debug("Calculating accuracy for catch the beat")

        acc = (count_50 + count_100 + count_300) / (
            count_katu
            + count_miss
            + count_50
            + count_100
            + count_300
        )

    if mode == Mode.MANIA:
        if glob.debug:
            log.debug("Calculating accuracy for mania")

        acc = (
            50 * count_50
            + 100 * count_100
            + 200 * count_katu
            + 300 * (count_300 + count_geki)
        ) / (
            300
            * (
                count_miss
                + count_50
                + count_100
                + count_katu
                + count_300
                + count_geki
            )
        )

    return acc * 100