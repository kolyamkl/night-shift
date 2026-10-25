from app.ingest import Line
from app.ingest.layout import assemble, group_rows


def line(text, x0, y0, x1=None, height=0.02, conf=1.0):
    return Line(text=text, bbox=(x0, y0, x1 if x1 is not None else x0 + 0.3, y0 + height), confidence=conf)


def test_pieces_on_one_row_are_joined_left_to_right():
    rows = group_rows([line("Account:", 0.1, 0.100), line("41960183", 0.5, 0.102), line("Name: Ann", 0.1, 0.13)])
    assert [[ln.text for ln in row] for row in rows] == [["Account:", "41960183"], ["Name: Ann"]]


def test_rows_read_top_to_bottom_whatever_the_input_order():
    text = assemble([line("third", 0.1, 0.16), line("first", 0.1, 0.10), line("second", 0.1, 0.13)])
    assert text == "first\nsecond\nthird"


def test_a_large_gap_starts_a_new_paragraph():
    # Rows 0.02 high: 0.01 between rows inside a paragraph, 0.05 before the next paragraph.
    text = assemble(
        [
            line("Dear Ann,", 0.1, 0.10),
            line("Thanks for", 0.1, 0.13),
            line("your letter.", 0.1, 0.16),
            line("Kind regards,", 0.1, 0.23),
        ]
    )
    assert text == "Dear Ann,\nThanks for\nyour letter.\n\nKind regards,"


def test_blank_input():
    assert assemble([]) == ""
    assert assemble([line("   ", 0.1, 0.1)]) == ""
