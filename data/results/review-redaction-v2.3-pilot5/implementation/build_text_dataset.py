"""Version the existing synthetic data for exact-text extraction; no API calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from build import SPLITS, write_jsonl
from contract import redact
from text_detection import TASK_VERSION, SYSTEM_PROMPT, gold_extraction, model_request, resolve

ROOT = Path(__file__).resolve().parents[2]


def convert(record):
    row = deepcopy(record)
    row['source_record_id'] = row['id']
    row['id'] = row['id'].replace(row['task_version'], TASK_VERSION, 1)
    row['task_version'] = TASK_VERSION
    row['expected_extraction'] = gold_extraction(row['input'], row['expected_detection'])
    assert redact(row['input'], resolve(row['input'], row['expected_extraction']))[0] == row['expected_redacted']
    return row


def main():
    out = ROOT / 'data/review_redaction_v2_3'
    counts = {}
    for split in SPLITS:
        rows = [convert(json.loads(line)) for line in
                (ROOT / 'data/review_redaction_v2' / f'{split}.jsonl').read_text().splitlines()]
        write_jsonl(out / f'{split}.jsonl', rows)
        write_jsonl(out / 'teacher_requests' / f'{split}.jsonl', [model_request(r) for r in rows])
        counts[split] = len(rows)
    (out / 'system_prompt.txt').write_text(SYSTEM_PROMPT)
    manifest = {'task_version': TASK_VERSION, 'source': 'data/review_redaction_v2',
                'same_inputs_and_splits': True, 'counts': counts,
                'system_prompt_sha256': hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest))


if __name__ == '__main__':
    main()
