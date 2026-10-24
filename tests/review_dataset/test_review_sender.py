from copy import deepcopy
import json

import pytest

from build import make_record, TEMPLATES
from send_review_batch import evaluate, exclude_prior_runs, pending_records, prepare, select_records


def test_balanced_selection_excludes_holdout():
    records = [make_record('train', family, i) for family in TEMPLATES for i in range(24)]
    selected = select_records(records, 40)
    assert len(selected) == len({r['id'] for r in selected}) == 40
    assert {r['scenario'] for r in selected} == set(TEMPLATES)
    assert selected == select_records(records, 40)
    with pytest.raises(ValueError, match='synthetic training'):
        select_records(records + [make_record('eval', 'contact', 0)], 40)


def test_validation_rejects_bad_offsets_and_truncation():
    row = make_record('train', 'contact', 0)
    assert evaluate(row, json.dumps(row['expected_detection']), 'end_turn')['exact_gold']
    broken = deepcopy(row['expected_detection'])
    broken['entities'][0]['start'] += 1
    assert not evaluate(row, json.dumps(broken), 'end_turn')['valid']
    assert not evaluate(row, json.dumps(row['expected_detection']), 'max_tokens')['valid']
    assert not evaluate(row, '```json\n{}\n```', 'end_turn')['valid']
    missing = evaluate(row, '{"entities":[]}', 'end_turn')
    assert missing['valid'] and not missing['exact_gold'] and missing['false_negative'] > 0


def test_resume_skips_invalid_success_and_uncertain_calls(tmp_path):
    records = [make_record('train', 'contact', i) for i in range(3)]
    attempts = [{'id': records[0]['id']}]
    results = [{'id': records[1]['id'], 'api_success': True, 'evaluation': {'valid': False}}]
    assert pending_records(records, attempts, results) == [records[2]]
    prepare(tmp_path, records)
    prepare(tmp_path, records)
    changed = deepcopy(records)
    changed[0]['input']['question'] += ' Extra'
    with pytest.raises(ValueError, match='Frozen batch differs'):
        prepare(tmp_path, changed)


def test_additional_batch_excludes_all_prior_attempts(tmp_path):
    records = [make_record('train', family, i) for family in TEMPLATES for i in range(24)]
    first = select_records(records, 40)
    prepare(tmp_path, first)
    # Exclude even attempts with no saved response; never duplicate uncertain calls.
    (tmp_path / 'attempts.jsonl').write_text(''.join(json.dumps({'id': r['id']}) + '\n' for r in first))
    second = select_records(exclude_prior_runs(records, [tmp_path]), 40)
    assert not {r['id'] for r in first} & {r['id'] for r in second}
    assert len(second) == 40
    assert {r['scenario'] for r in second} == set(TEMPLATES)
    with pytest.raises(ValueError, match='Prior run'):
        exclude_prior_runs(records, [tmp_path / 'missing'])


def test_exclusion_follows_source_record_across_versions(tmp_path):
    old = make_record('train', 'contact', 5)
    prepare(tmp_path, [old])
    (tmp_path / 'attempts.jsonl').write_text(json.dumps({'id': old['id']}) + '\n')
    revised = {**old, 'id': 'new-task-contact-005', 'source_record_id': old['id']}
    untouched = make_record('train', 'contact', 6)
    assert exclude_prior_runs([revised, untouched], [tmp_path]) == [untouched]
