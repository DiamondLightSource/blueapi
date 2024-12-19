import os


def current_umask() -> int:
    # You can't get the current umask without changing it
    tmp = os.umask(0o022)
    os.umask(tmp)
    return tmp
