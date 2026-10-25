from copy import deepcopy
import json
from pathlib import Path

import pytest

from build import make_record
from build_text_dataset import convert
from contract import redact
from send_review_batch import evaluate, model_request, prepare
from text_detection import (TASK_VERSION, TOOL_NAME, TextReviewSession, gold_extraction,
                            resolve, response_extraction, context_warnings, SYSTEM_PROMPT)


def response(extraction, **changes):
    return {'stop_reason': 'tool_use', 'content': [
        {'type': 'tool_use', 'name': TOOL_NAME, 'input': extraction}], **changes}


def entry(text, eid='person', before='', after='', kind='PERSON'):
    return dict(text=text, entity_id=eid, type=kind, before=before, after=after)


def test_reported_rose_case_includes_question_and_correct_local_offsets():
    row = convert(make_record('train', 'contact', 5))
    extraction = row['expected_extraction']
    result = evaluate(row, '', 'tool_use', response(extraction))
    assert result['valid'] and result['exact_gold']
    marks = result['resolved_detection']['entities']
    assert [(e['start'], e['end']) for e in marks] == [(8, 25), (39, 60), (62, 103), (104, 111), (118, 137), (145, 160), (4, 8)]
    assert result['redacted']['question'] == 'Can [VEIL_PERSON_1] give notice on 6 November 2026?'
    omitted = deepcopy(extraction)
    omitted['question'] = []
    missed = evaluate(row, '', 'tool_use', response(omitted))
    assert missed['valid'] and not missed['exact_gold']
    assert missed['false_negative'] == 1 and missed['missing_entities'][0]['text'] == 'Rose'


def test_unique_context_distinguishes_person_from_common_word():
    bundle = {'document': 'May signed in May.', 'question': ''}
    extraction = {'document': [entry('May')], 'question': []}
    with pytest.raises(ValueError, match='found 2'):
        resolve(bundle, extraction)
    extraction['document'][0]['after'] = ' signed'
    assert redact(bundle, resolve(bundle, extraction))[0]['document'] == '[VEIL_PERSON_1] signed in May.'


def test_repeated_mentions_can_share_identity_without_blanket_replacement():
    bundle = {'document': 'Rose met Rose.', 'question': 'Ask Rose.'}
    extraction = {'document': [entry('Rose', after=' met'), entry('Rose', before='met ')],
                  'question': [entry('Rose')]}
    output = redact(bundle, resolve(bundle, extraction))[0]
    assert output == {'document': '[VEIL_PERSON_1] met [VEIL_PERSON_1].', 'question': 'Ask [VEIL_PERSON_1].'}


def test_unicode_crlf_and_newlines_are_preserved():
    bundle = {'document': '🔒 Zoë’s address: 12 Test Lane\r\nExampleton.', 'question': 'Ask Zoë?'}
    extraction = {'document': [entry('Zoë'), entry('12 Test Lane\r\nExampleton', eid='home', kind='ADDRESS')],
                  'question': [entry('Zoë')]}
    marks = resolve(bundle, extraction)
    assert marks['entities'][0]['start'] == 2
    output = redact(bundle, marks)[0]
    assert output['document'] == '🔒 [VEIL_PERSON_1]’s address: [VEIL_ADDRESS_1]\r\n[VEIL_ADDRESS_1].'


@pytest.mark.parametrize('damage', ['missing_question', 'approval', 'offset', 'bad_context', 'invented_text',
                                  'duplicate', 'overlap', 'unknown_type', 'empty', 'invalid_id'])
def test_invalid_extraction_blocks_and_clears_existing_approval(damage):
    row = convert(make_record('train', 'contact', 5))
    extraction = deepcopy(row['expected_extraction'])
    session = TextReviewSession(row['input'], extraction, 'openai')
    session.approve(session.preview()['review_id'], confirmed=True)
    if damage == 'missing_question': del extraction['question']
    elif damage == 'approval': extraction['approved'] = True
    elif damage == 'offset': extraction['document'][0]['start'] = 8
    elif damage == 'bad_context': extraction['document'][0].update(text='a', before='not here')
    elif damage == 'invented_text': extraction['document'][0]['text'] = 'Rosie Fictional'
    elif damage == 'duplicate': extraction['document'].append(deepcopy(extraction['document'][0]))
    elif damage == 'overlap': extraction['document'].append(entry('Alderwickaag'))
    elif damage == 'unknown_type': extraction['question'][0]['type'] = 'APPROVED'
    elif damage == 'empty': extraction['document'][0]['text'] = ''
    elif damage == 'invalid_id': extraction['document'][0]['entity_id'] = 'Bad ID'
    with pytest.raises(ValueError): session.update(row['input'], extraction, 'openai')
    with pytest.raises(PermissionError): session.outbound()


def test_exact_text_review_still_requires_human_approval_and_reconfirmation():
    row = convert(make_record('train', 'contact', 5))
    session = TextReviewSession(row['input'], row['expected_extraction'], 'openai')
    with pytest.raises(PermissionError): session.outbound()
    old = session.preview()['review_id']
    session.approve(old, confirmed=True)
    assert set(session.outbound()) == {'destination', 'document', 'question'}
    session.update(row['input'], row['expected_extraction'], 'anthropic')
    with pytest.raises(PermissionError): session.approve(old, confirmed=True)
    with pytest.raises(PermissionError): session.outbound()


@pytest.mark.parametrize('bad', [
    {'stop_reason': 'max_tokens', 'content': []},
    {'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': '```json\n{}\n```'}]},
    {'stop_reason': 'tool_use', 'content': []},
    {'stop_reason': 'tool_use', 'content': [{'type': 'tool_use', 'name': 'approve_send', 'input': {}}]},
    {'stop_reason': 'tool_use', 'content': [{'type': 'tool_use', 'name': TOOL_NAME, 'input': {}}] * 2},
])
def test_wrong_response_shape_rejected(bad):
    with pytest.raises(ValueError): response_extraction(bad)


def test_new_request_schema_has_no_gold_or_numeric_offsets():
    row = convert(make_record('train', 'contact', 5))
    req = model_request(row)['request']
    assert json.loads(req['messages'][0]['content']) == row['input']
    assert req['tool_choice']['name'] == TOOL_NAME
    assert req['tools'][0]['strict'] is True
    fields = req['tools'][0]['input_schema']['properties']['document']['items']['properties']
    assert 'start' not in fields and 'end' not in fields
    assert set(req['tools'][0]['input_schema']['required']) == {'document', 'question'}
    assert model_request(convert(make_record('eval', 'contact', 0)))['extra_headers'] == {'x-middleware-record': 'off'}


def test_versions_cannot_share_run_directory(tmp_path):
    old = make_record('train', 'contact', 5)
    prepare(tmp_path, [old])
    with pytest.raises(ValueError, match='Frozen batch differs'): prepare(tmp_path, [convert(old)])


def test_diagnostic_recording_policy_is_frozen_with_requests(tmp_path):
    row = convert(make_record('train', 'contact', 5))
    diagnostic = {**row, 'recording': 'off'}
    assert model_request(diagnostic)['extra_headers'] == {'x-middleware-record': 'off'}
    prepare(tmp_path, [diagnostic])
    with pytest.raises(ValueError, match='Frozen batch differs'): prepare(tmp_path, [row])


def test_all_converted_fixtures_match_gold_and_keep_original_splits():
    root = Path(__file__).resolve().parents[3] / 'data'
    for split in ('train', 'fresh', 'eval'):
        old = [json.loads(line) for line in (root/'review_redaction_v2'/f'{split}.jsonl').read_text().splitlines()]
        new = [json.loads(line) for line in (root/'review_redaction_v2_4'/f'{split}.jsonl').read_text().splitlines()]
        assert new == [convert(r) for r in old]
        exports = [json.loads(line) for line in (root/'review_redaction_v2_4'/'teacher_requests'/f'{split}.jsonl').read_text().splitlines()]
        assert exports == [model_request(row) for row in new]
        for row in new:
            assert row['task_version'] == TASK_VERSION and row['split'] == split
            assert redact(row['input'], resolve(row['input'], row['expected_extraction']))[0] == row['expected_redacted']
    assert (root/'review_redaction_v2_4'/'system_prompt.txt').read_text() == SYSTEM_PROMPT


def test_reused_owner_labels_are_separated_by_type_locally():
    bundle = {'document': 'Rose email rose@example.test', 'question': 'Ask Rose.'}
    extraction = {'document': [entry('Rose', eid='rose'), entry('rose@example.test', eid='rose', kind='EMAIL')],
                  'question': [entry('Rose', eid='rose')]}
    detection = resolve(bundle, extraction)
    assert detection['entities'][0]['entity_id'] != detection['entities'][1]['entity_id']
    assert detection['entities'][0]['entity_id'] == detection['entities'][2]['entity_id']
    assert redact(bundle, detection)[0] == {'document': '[VEIL_PERSON_1] email [VEIL_EMAIL_1]',
                                           'question': 'Ask [VEIL_PERSON_1].'}


def test_context_is_only_used_to_disambiguate_exact_repeated_quotes():
    bundle = {'document': 'Rose met May in May.', 'question': ''}
    extraction = {'document': [entry('Rose', after=' invented hint')], 'question': []}
    assert resolve(bundle, extraction)['entities'][0]['start'] == 0
    assert len(context_warnings(bundle, extraction)) == 1
    extraction['document'] = [entry('May', after=' invented hint')]
    with pytest.raises(ValueError, match='found 0'): resolve(bundle, extraction)
    extraction['document'] = [entry('Rosie')]
    with pytest.raises(ValueError, match='found 0'): resolve(bundle, extraction)
