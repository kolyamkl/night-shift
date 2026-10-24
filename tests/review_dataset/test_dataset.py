from copy import deepcopy
import json
from pathlib import Path

import pytest

from build import COUNTS, SPLITS, TEMPLATES, make_record, model_request, run_workflow_case, validate, workflow_cases
from contract import ENTITY_TYPES, redact
from prompt import SYSTEM_PROMPT

DATA = Path(__file__).resolve().parents[2] / 'data' / 'review_redaction_v2'


@pytest.fixture(scope='module')
def records():
    return {split: [make_record(split, family, i) for family in TEMPLATES
                   for i in range(COUNTS[split])] for split in SPLITS}


def test_split_coverage_and_holdout(records):
    stats = validate(records)
    for split in SPLITS:
        assert stats[split]['records'] == COUNTS[split] * len(TEMPLATES)
        assert stats[split]['clean_records'] == COUNTS[split]
        for kind in ('BANK_ACCOUNT', 'SORT_CODE', 'IBAN', 'CARD', 'NI_NUMBER'):
            assert stats[split]['entity_occurrences'][kind] >= 20
    literal_templates = [pair for variants in TEMPLATES.values() for pair in variants]
    assert len(literal_templates) == len(set(literal_templates))


def test_committed_dataset_matches_generator(records):
    for split in SPLITS:
        actual = [json.loads(line) for line in (DATA / f'{split}.jsonl').read_text().splitlines()]
        assert actual == records[split]
        exports = [json.loads(line) for line in (DATA / 'teacher_requests' / f'{split}.jsonl').read_text().splitlines()]
        assert exports == [model_request(row) for row in records[split]]
    assert json.loads((DATA/'manifest.json').read_text())['splits'] == validate(records)
    assert (DATA/'system_prompt.txt').read_text() == SYSTEM_PROMPT


def test_every_span_is_grounded_and_replaced(records):
    for rows in records.values():
        for row in rows:
            for ent in row['expected_detection']['entities']:
                assert row['input'][ent['source']][ent['start']:ent['end']] == ent['text']
            assert redact(row['input'], row['expected_detection'])[0] == row['expected_redacted']
            assert row['requires_user_confirmation'] is True


def test_model_requests_never_include_answer_keys_or_approval(records):
    for split in SPLITS:
        for row in records[split]:
            export = model_request(row)
            message = json.loads(export['request']['messages'][0]['content'])
            assert message == row['input']
            assert set(message) == {'document', 'question'}
            assert set(export['request']) == {'model', 'system', 'max_tokens', 'messages', 'metadata'}
            assert export['extra_headers'] == ({'x-middleware-record': 'off'} if split == 'eval' else {})


@pytest.mark.parametrize('case', workflow_cases(), ids=lambda case: case['id'])
def test_workflow_fixtures(case):
    assert run_workflow_case(case) == case['expected_allow_send']


def test_validator_rejects_template_leakage(records):
    changed = deepcopy(records)
    changed['eval'][0]['template_id'] = changed['train'][0]['template_id']
    with pytest.raises(ValueError, match='Template leaks'):
        validate(changed)


def test_prompt_covers_types_and_leaves_approval_to_app():
    for kind in ENTITY_TYPES:
        assert f'- {kind}:' in SYSTEM_PROMPT
    assert 'Do not rewrite' in SYSTEM_PROMPT
    assert 'user must approve' in SYSTEM_PROMPT
