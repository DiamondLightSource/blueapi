from .cli import main

__all__ = ["main"]

DEPRECATION_MESSAGE = (
    "WARNING! This command is deprecated, please use >>blueapi instead!"
)

print("*" * len(DEPRECATION_MESSAGE))
print(DEPRECATION_MESSAGE)
print("*" * len(DEPRECATION_MESSAGE))
