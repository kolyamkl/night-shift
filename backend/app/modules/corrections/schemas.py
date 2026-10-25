from pydantic import BaseModel


class Correction(BaseModel):
    action: str  # "hide" or "unhide"; anything else is a 400 with a message, not a 422
    text: str
    type: str = "CUSTOM"
