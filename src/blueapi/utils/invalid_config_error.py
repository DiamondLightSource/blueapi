class InvalidConfigError(Exception):
    def __init__(self, message="Configuration is invalid"):
        super().__init__(message)
