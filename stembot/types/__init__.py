from enum import Enum

class UpperCaseStrEnum(str, Enum):
    """A string enum that converts to uppercase string representation."""
    def __str__(self) -> str:
        return str(self.value).upper()
