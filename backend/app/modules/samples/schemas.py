from pydantic import BaseModel


class SampleCard(BaseModel):
    """What a sample card shows: the document's own title, its pages and how many personal values it holds."""

    name: str  # the PDF's file name, the sample's id
    label: str  # from the file name: "05_nda.pdf" -> "NDA"
    title: str  # the first line of its text when a gold file has it, else the label
    kind: str
    pages: int
    values: int | None  # personal values in the gold file, if there is one
    types: dict[str, int]
