from pydantic import BaseModel


class Ask(BaseModel):
    question: str


class Answer(BaseModel):
    answer: str  # with the real values put back
    answer_with_placeholders: str  # as the model wrote it
    sent_text: str  # the redacted document the model saw
    sent_question: str  # the question the model saw, pseudonymised
    unknown_placeholders: list[str]
    mreq_id: str | None
    turn_id: int
    created_at: str
