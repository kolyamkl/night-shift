import pytest
from evalkit.redact import Vault, restore
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline import T1Result
from app.question import plain, pseudonymise


@pytest.fixture
def vault():
    v = Vault()
    for value, etype in [("Daryna Shevchenko", "PERSON"), ("Ben Poole", "PERSON"), ("Tomasz Wierzbicki", "PERSON"),
                         ("Piotr Wierzbicki", "PERSON"), ("237 Little Court, Bristol", "ADDRESS"),
                         ("NPM-404605", "CUSTOM"), ("Kenji Morioka-Grant", "PERSON")]:
        v.placeholder_for(value, etype)
    return v


@pytest.mark.parametrize("question, sent", [
    ("When can Daryna Shevchenko end the tenancy?", "When can [PERSON_1] end the tenancy?"),
    ("when can daryna  shevchenko leave?", "when can [PERSON_1] leave?"),
    ("Does Daryna pay the deposit?", "Does [PERSON_1] pay the deposit?"),
    ("Has Morioka signed?", "Has [PERSON_5] signed?"),
    ("Is 237 Little Court Bristol the property?", "Is [ADDRESS_1] the property?"),
    ("What does tenant NPM-404605 owe?", "What does tenant [CUSTOM_1] owe?"),
])
def test_known_values_and_name_parts_become_the_document_placeholders(vault, question, sent):
    assert pseudonymise(question, vault)[0] == sent


def test_a_surname_two_people_share_is_hidden_without_pointing_at_either(vault):
    sent, local = pseudonymise("Is Wierzbicki on the lease?", vault)
    assert sent == "Is [PERSON_6] on the lease?"
    assert local.by_placeholder["[PERSON_6]"] == "Wierzbicki"


def test_new_values_get_new_placeholders_and_come_back_in_the_answer(vault):
    sent, local = pseudonymise("Email ann.lee@post.example or call 07700 900123 about it.", vault)
    assert sent == "Email [EMAIL_1] or call [PHONE_1] about it."
    assert restore("Write to [EMAIL_1].", local)[0] == "Write to ann.lee@post.example."
    assert "[EMAIL_1]" not in vault.by_placeholder  # the stored vault is not changed


@pytest.mark.parametrize("question", ["Will the landlord grant consent?", "When is the rent due?"])
def test_ordinary_words_stay_as_they_are(vault, question):
    assert pseudonymise(question, vault)[0] == question


def test_a_lower_case_word_is_not_taken_for_a_short_name_part(vault):
    vault.placeholder_for("Will Grant", "PERSON")  # [PERSON_6]
    # "grant" is lower case and shorter than six letters; a capital "Will" is hidden, to be safe.
    assert pseudonymise("Will the landlord grant consent?", vault)[0] == "[PERSON_6] the landlord grant consent?"


def test_plain_takes_out_markdown_but_keeps_arithmetic():
    assert plain("The total is **£373.47** and __due__ *now*.") == "The total is £373.47 and due now."
    assert plain("# Summary\n* one\n+ two\nRate 5 * 3 stays.") == "Summary\n- one\n- two\nRate 5 * 3 stays."


@pytest.fixture
def client(postgres_store):
    seen = []

    def t1_factory(doc_id):
        def t1(chunk):
            return T1Result([{"text": "Raj Patel", "type": "PERSON"}] if "Raj Patel" in chunk else [], "mreq_test", None)
        return t1

    def t2(question, redacted_text):
        seen.append((question, redacted_text))
        return "**[PERSON_1]** can leave with two months' notice.", "mreq_answer"

    app.state.t1_factory, app.state.t2 = t1_factory, t2
    with TestClient(app, headers={"X-Veil-Request": "1"}, client=(postgres_store.test_suffix, 50000)) as test_client:
        assert test_client.post("/api/auth/register", json={
            "email": f"q-{postgres_store.test_suffix}@example.test", "password": "test-password"}).status_code == 201
        test_client.seen = seen
        yield test_client
    app.state.t1_factory = app.state.t2 = None


def test_the_ai_never_sees_a_name_typed_in_the_question(client):
    doc = client.post("/api/documents", data={"text": "Tenant: Raj Patel. Rent 950."}).json()
    client.post(f"/api/documents/{doc['doc_id']}/redact")
    ans = client.post(f"/api/documents/{doc['doc_id']}/ask", json={"question": "When can Raj Patel leave?"}).json()
    question, text = client.seen[-1]
    assert question == "When can [PERSON_1] leave?" and "Patel" not in question + text
    assert ans["sent_question"] == question
    assert ans["answer"] == "Raj Patel can leave with two months' notice."
    assert ans["answer_with_placeholders"] == "[PERSON_1] can leave with two months' notice."
    turns = client.get(f"/api/documents/{doc['doc_id']}").json()["turns"]
    assert turns[-1]["question"] == "When can Raj Patel leave?" and turns[-1]["sent_question"] == question
