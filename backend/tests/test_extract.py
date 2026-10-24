from app.domain.extract import extract_pdf, extract_text


def test_plain_text_becomes_a_document_without_boxes():
    doc = extract_text("My name is Jo Smith.")
    assert doc.kind == "text"
    assert doc.text == "My name is Jo Smith."
    assert doc.words == []


def test_pdf_words_map_back_to_their_characters(tenancy_pdf):
    doc = extract_pdf(tenancy_pdf, "lease.pdf")
    assert doc.kind == "pdf"
    assert len(doc.pages) == 2
    for w in doc.words:
        assert doc.text[w.start:w.end] == w.text
    patel = [w for w in doc.words if w.text == "Patel"]
    assert [w.page for w in patel] == [0, 1]
    assert patel[0].bbox[0] > 72  # to the right of "Tenant:" and "Raj"


def test_pdf_text_keeps_lines_and_blocks_apart(tenancy_pdf):
    doc = extract_pdf(tenancy_pdf, "lease.pdf")
    assert "Tenant: Raj Patel\nAddress: 12 Oak Road, Leeds LS6 2AB" in doc.text
    assert "Tenancy agreement\n\n" in doc.text
