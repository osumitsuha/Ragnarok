import colored


class Asora:
    DEBUG = colored.fg(107)
    INFO = colored.fg(111)
    CHAT = colored.fg(177)
    WARNING = colored.fg(130)
    ERROR = colored.fg(124)

    RESET = colored.attr("reset")


def info(msg: str) -> str:
    print(f"[{Asora.INFO}info{Asora.RESET}]\t  {msg}")


def chat(msg: str) -> str:
    print(f"[{Asora.CHAT}chat{Asora.RESET}]\t  {msg}")


def debug(msg: str) -> str:
    print(f"[{Asora.DEBUG}debug{Asora.RESET}]\t  {msg}")


def warn(msg: str) -> str:
    print(f"[{Asora.WARNING}warn{Asora.RESET}]\t  {msg}")


def error(msg: str) -> str:
    print(f"[{Asora.ERROR}error{Asora.RESET}]\t  {msg}")


def fail(msg: str) -> str:
    print(f"[{Asora.ERROR}fail{Asora.RESET}]\t  {msg}")
