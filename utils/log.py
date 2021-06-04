import colored

class Asora:
    DEBUG = colored.bg(107)
    INFO = colored.bg(111)
    WARNING = colored.bg(130)
    ERROR = colored.bg(160)

    RESET = colored.attr('reset')

def info(msg: str) -> str:
    print(f"{Asora.INFO}[!]{Asora.RESET}\t  {msg}")

def debug(msg: str) -> str:
    print(f"{Asora.DEBUG}[?]{Asora.RESET}\t  {msg}")

def warning(msg: str ) -> str:
    print(f"{Asora.WARNING}[!?]{Asora.RESET}\t  {msg}")

def error(msg: str ) -> str:
    print(f"{Asora.ERROR}[X]{Asora.RESET}\t  {msg}")