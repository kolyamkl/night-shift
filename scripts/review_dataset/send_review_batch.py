"""Send a frozen synthetic train batch through Mubit; dry run unless --send.

Started calls are journalled before dispatch and never automatically retried,
including calls whose result was lost after interruption. Local validation cannot
remove a response from Mubit training. No adapter readiness is inferred here.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

from build import model_request as legacy_model_request
from contract import redact
from prompt import TASK_VERSION
import text_detection

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = 'https://api.mubit.ai/anthropic'


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def model_request(record):
    if record['task_version'] == text_detection.TASK_VERSION:
        export = text_detection.model_request(record)
    elif record['task_version'] == TASK_VERSION:
        export = legacy_model_request(record)
    else:
        raise ValueError('Unknown task version')
    if record.get('recording') == 'off':
        export['extra_headers'] = {'x-middleware-record': 'off'}
    return export


def select_records(records, limit, task_version=TASK_VERSION):
    if not 1 <= limit <= len(records):
        raise ValueError('Limit must fit the training dataset')
    groups = defaultdict(list)
    for row in records:
        if row['split'] != 'train' or row['synthetic'] is not True or row['task_version'] != task_version:
            raise ValueError('Only synthetic training records for this task are allowed')
        groups[row['scenario']].append(row)
    # Stable hash order varies fills; round robin covers every family before repeats.
    for rows in groups.values():
        rows.sort(key=lambda row: digest(row['id']))
    selected = []
    while len(selected) < limit:
        for rows in groups.values():
            if rows and len(selected) < limit:
                selected.append(rows.pop(0))
    if len({row['id'] for row in selected}) != limit:
        raise ValueError('Duplicate record IDs')
    return selected


def evaluate(record, text, stop_reason, response=None):
    result = {'valid': False, 'exact_gold': False}
    try:
        if record['task_version'] == text_detection.TASK_VERSION:
            extraction = text_detection.response_extraction(response or {})
            detection = text_detection.resolve(record['input'], extraction)
            result['extraction'] = extraction
            result['resolved_detection'] = detection
            result['context_warnings'] = text_detection.context_warnings(record['input'], extraction)
        else:
            if stop_reason != 'end_turn':
                raise ValueError('Incomplete response: ' + str(stop_reason))
            detection = json.loads(text)
        output, _ = redact(record['input'], detection)
        key = lambda e: (e['source'], e['start'], e['end'], e['type'])
        predicted = {key(e) for e in detection['entities']}
        gold = {key(e) for e in record['expected_detection']['entities']}
        result.update(valid=True, redacted=output, true_positive=len(predicted & gold),
                      false_positive=len(predicted - gold), false_negative=len(gold - predicted),
                      exact_gold=output == record['expected_redacted'],
                      missing_entities=[e for e in record['expected_detection']['entities'] if key(e) not in predicted])
    except (ValueError, TypeError, KeyError) as exc:
        result['validation_error'] = str(exc)
    return result


def load_key():
    key = os.environ.get('MUBIT_API_KEY')
    if not key:
        for line in (ROOT / '.env').read_text().splitlines():
            name, sep, value = line.strip().partition('=')
            if sep and name == 'MUBIT_API_KEY':
                key = value.strip().strip('\"\'')
                break
    if not key or not key.startswith('mbt_'):
        raise ValueError('A Mubit API key is required in the environment or .env')
    # Do not let a second provider credential be added by the SDK.
    os.environ.pop('ANTHROPIC_AUTH_TOKEN', None)
    return key


def send_one(record, key):
    import anthropic
    started = time.monotonic()
    result = {'id': record['id'], 'scenario': record['scenario'],
              'timestamp': datetime.now(timezone.utc).isoformat(), 'api_success': False}
    try:
        with anthropic.Anthropic(api_key=key, base_url=BASE_URL, max_retries=0, timeout=600) as client:
            export = model_request(record)
            raw = client.messages.with_raw_response.create(**export['request'], extra_headers=export['extra_headers'])
            message = raw.parse()
            body = ''.join(block.text for block in message.content if block.type == 'text')
            result.update(api_success=True, request_id=raw.headers.get('x-middleware-request-id'),
                          model=message.model, stop_reason=message.stop_reason,
                          response=message.model_dump(mode='json'), text=body,
                          evaluation=evaluate(record, body, message.stop_reason, message.model_dump(mode='json')))
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error=str(exc).replace(key, '[REDACTED]'))
    result['seconds'] = round(time.monotonic() - started, 3)
    # Defense in depth: no credential may enter persisted output.
    return json.loads(json.dumps(result).replace(key, '[REDACTED]'))


def append_row(path, row):
    with path.open('a') as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def prepare(out, selected):
    if not selected or len({row['task_version'] for row in selected}) != 1:
        raise ValueError('Run must contain exactly one task version')
    manifest = {'task_version': selected[0]['task_version'], 'base_url': BASE_URL,
                'selection_hash': digest(selected),
                'request_hash': digest([model_request(row) for row in selected]),
                'ids': [row['id'] for row in selected],
                'scenarios': dict(Counter(row['scenario'] for row in selected))}
    path = out / 'run.json'
    if path.exists():
        if json.loads(path.read_text()) != manifest:
            raise ValueError('Frozen batch differs; do not reuse this run directory')
    else:
        path.write_text(json.dumps(manifest, indent=2) + '\n')
        (out / 'selected_train.jsonl').write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in selected))
        (out / 'requests.jsonl').write_text(''.join(json.dumps(model_request(row), ensure_ascii=False) + '\n' for row in selected))
    return manifest


def pending_records(selected, attempts, results):
    attempted = {row['id'] for row in attempts + results}
    return [row for row in selected if row['id'] not in attempted]


def exclude_prior_runs(records, paths):
    attempts, results = [], []
    for path in paths:
        if not (path / 'run.json').is_file() or not (path / 'attempts.jsonl').is_file():
            raise ValueError(f'Prior run has no manifest or attempt journal: {path}')
        attempts.extend(read_rows(path / 'attempts.jsonl'))
        results.extend(read_rows(path / 'responses.jsonl'))
    attempted = {row['id'] for row in attempts + results}
    return [row for row in records if row['id'] not in attempted
            and row.get('source_record_id') not in attempted]


def summarize(out, manifest):
    rows = read_rows(out / 'responses.jsonl')
    valid = [r for r in rows if r.get('evaluation', {}).get('valid')]
    usage = Counter()
    for row in rows:
        for name, value in row.get('response', {}).get('usage', {}).items():
            if type(value) is int:
                usage[name] += value
    summary = {'selected': len(manifest['ids']), 'attempts': len(read_rows(out / 'attempts.jsonl')),
               'responses_saved': len(rows), 'api_success': sum(r['api_success'] for r in rows),
               'mubit_request_ids': sum(bool(r.get('request_id')) for r in rows),
               'valid_detection': len(valid), 'exact_gold_redaction': sum(r['evaluation']['exact_gold'] for r in valid),
               'validation_errors': dict(Counter(r['evaluation']['validation_error'] for r in rows
                                               if r.get('evaluation', {}).get('validation_error'))),
               'usage': dict(usage), 'adapter_status': 'unverified',
               'note': 'Training sample diagnostics, not held-out evaluation. Invalid responses are failures, not corrected labels.'}
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=40)
    parser.add_argument('--max-new', type=int, default=40)
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=4)
    parser.add_argument('--task-version', choices=[TASK_VERSION, text_detection.TASK_VERSION], default=text_detection.TASK_VERSION)
    parser.add_argument('--record-id', action='append', default=[], help='Explicit pilot record ID; repeat; count must equal limit')
    parser.add_argument('--no-record', action='store_true', help='Synthetic diagnostic calls only; request no Mubit recording/training')
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--exclude-run', type=Path, action='append', default=[],
                        help='Exclude attempted IDs from a prior run; repeat for multiple runs')
    parser.add_argument('--send', action='store_true')
    args = parser.parse_args()
    if args.max_new < 1:
        parser.error('--max-new must be positive')
    if args.out_dir is None:
        if args.task_version != TASK_VERSION:
            parser.error('New task versions require an explicit separate --out-dir')
        args.out_dir = ROOT / 'data/results/review-redaction-v2.1-40'
    dataset = 'review_redaction_v2_4' if args.task_version == text_detection.TASK_VERSION else 'review_redaction_v2'
    records = exclude_prior_runs(read_rows(ROOT / 'data' / dataset / 'train.jsonl'), args.exclude_run)
    selected = select_records(records, args.limit, args.task_version)
    if args.record_id:
        by_id = {r['id']: r for r in records}
        if len(args.record_id) != args.limit or len(set(args.record_id)) != args.limit or any(i not in by_id for i in args.record_id):
            parser.error('Explicit IDs must be distinct available training records and match --limit')
        selected = [by_id[i] for i in args.record_id]
    if args.no_record:
        selected = [{**row, 'recording': 'off'} for row in selected]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / '.sender.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = prepare(args.out_dir, selected)
        pending = pending_records(selected, read_rows(args.out_dir / 'attempts.jsonl'),
                                  read_rows(args.out_dir / 'responses.jsonl'))[:args.max_new]
        print(f'Selected {len(selected)}; eligible new calls {len(pending)}; send={args.send}', flush=True)
        if args.send and pending:
            key = load_key()
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = []
                for record in pending:
                    append_row(args.out_dir / 'attempts.jsonl', {'id': record['id'], 'timestamp': datetime.now(timezone.utc).isoformat()})
                    futures.append(pool.submit(send_one, record, key))
                for future in as_completed(futures):
                    result = future.result()
                    append_row(args.out_dir / 'responses.jsonl', result)
                    print(f"{result['id']}: api_success={result['api_success']}, valid={result.get('evaluation', {}).get('valid', False)}", flush=True)
        summarize(args.out_dir, manifest)


if __name__ == '__main__':
    main()
