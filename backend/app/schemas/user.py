from pydantic import BaseModel


class EmailCheck(BaseModel):
    """Whether an account has this email; never whose (DL-66)."""

    email: str
    exists: bool


class UsernameSuggestion(BaseModel):
    """An available username suggested from a name, or null when none can be made (DL-66)."""

    suggestion: str | None
