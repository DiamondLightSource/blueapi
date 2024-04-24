class WorkerBusyError(Exception):
    def __init__(self, message):
        super().__init__(message)


class WorkerAlreadyStartedError(Exception):
    def __init__(self, message):
        super().__init__(message)
