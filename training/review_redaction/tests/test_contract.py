from copy import deepcopy

import pytest

from contract import ReviewSession, detector_payload, redact


def sample():
    bundle = {'document': '🔒 Rose’s address: 12 Test Lane\r\nExampleton.',
              'question': 'Can Rose pay £50 on 1 May?'}
    detection = {'entities': [
        {'source': 'document', 'start': 2, 'end': 6, 'text': 'Rose',
         'type': 'PERSON', 'entity_id': 'rose'},
        {'source': 'document', 'start': 18, 'end': 43, 'text': '12 Test Lane\r\nExampleton',
         'type': 'ADDRESS', 'entity_id': 'home'},
        {'source': 'question', 'start': 4, 'end': 8, 'text': 'Rose',
         'type': 'PERSON', 'entity_id': 'rose'},
    ]}
    # Explicitly locate the address; Unicode offsets are tested by the fixed Rose span.
    ent = detection['entities'][1]
    ent['start'] = bundle['document'].index(ent['text'])
    ent['end'] = ent['start'] + len(ent['text'])
    return bundle, detection


def test_exact_surrounding_text_newlines_and_cross_source_identity():
    bundle, detection = sample()
    output, vault = redact(bundle, detection)
    assert output == {
        'document': '🔒 [VEIL_PERSON_1]’s address: [VEIL_ADDRESS_1]\r\n[VEIL_ADDRESS_1].',
        'question': 'Can [VEIL_PERSON_1] pay £50 on 1 May?',
    }
    assert vault['[VEIL_PERSON_1]'] == ['Rose']


@pytest.mark.parametrize('damage', [
    'wrong_text', 'wrong_offset', 'overlap', 'boolean_offset', 'unknown_type',
    'unknown_source', 'extra_approval', 'conflicting_identity', 'empty_span',
])
def test_malformed_detection_blocks_review(damage):
    bundle, detection = sample()
    if damage == 'wrong_text':
        detection['entities'][0]['text'] = 'Rosie'
    elif damage == 'wrong_offset':
        detection['entities'][0]['start'] = 3
    elif damage == 'overlap':
        detection['entities'].append(deepcopy(detection['entities'][0]))
    elif damage == 'boolean_offset':
        detection['entities'][0]['start'] = True
    elif damage == 'unknown_type':
        detection['entities'][0]['type'] = 'APPROVED'
    elif damage == 'unknown_source':
        detection['entities'][0]['source'] = 'history'
    elif damage == 'extra_approval':
        detection['approved'] = True
    elif damage == 'conflicting_identity':
        detection['entities'][1]['entity_id'] = 'rose'
    elif damage == 'empty_span':
        detection['entities'][0].update(end=2, text='')
    with pytest.raises(ValueError):
        ReviewSession(bundle, detection, 'openai')


def test_no_send_until_explicit_confirmation_and_no_vault_in_payload():
    bundle, detection = sample()
    session = ReviewSession(bundle, detection, 'openai')
    with pytest.raises(PermissionError):
        session.outbound()
    preview = session.preview()
    with pytest.raises(PermissionError):
        session.approve(preview['review_id'], confirmed=False)
    session.approve(preview['review_id'], confirmed=True)
    payload = session.outbound()
    assert payload == {'destination': 'openai', **redact(bundle, detection)[0]}
    assert 'Rose' not in str(payload)
    assert set(payload) == {'destination', 'document', 'question'}


def test_preview_and_outbound_are_copies():
    bundle, detection = sample()
    session = ReviewSession(bundle, detection, 'anthropic')
    preview = session.preview()
    preview['payload']['question'] = 'tampered'
    assert session.preview()['payload']['question'] != 'tampered'
    session.approve(preview['review_id'], confirmed=True)
    payload = session.outbound()
    payload['document'] = 'tampered'
    assert session.outbound()['document'] != 'tampered'


def test_changes_invalidate_approval_even_if_redacted_preview_is_identical():
    bundle, detection = sample()
    session = ReviewSession(bundle, detection, 'openai')
    old = session.preview()['review_id']
    session.approve(old, confirmed=True)
    changed = {k: v.replace('Rose', 'Rosa') for k, v in bundle.items()}
    marks = deepcopy(detection)
    for ent in marks['entities']:
        if ent['text'] == 'Rose':
            ent['text'] = 'Rosa'
    session.update(changed, marks, 'openai')
    with pytest.raises(PermissionError):
        session.approve(old, confirmed=True)
    with pytest.raises(PermissionError):
        session.outbound()


def test_confirmation_cannot_be_replayed_between_sessions():
    bundle, detection = sample()
    first = ReviewSession(bundle, detection, 'openai')
    second = ReviewSession(bundle, detection, 'openai')
    with pytest.raises(PermissionError):
        second.approve(first.preview()['review_id'], confirmed=True)


def test_clean_text_still_needs_confirmation():
    session = ReviewSession({'document': 'Price £50.', 'question': 'When is it due?'},
                            {'entities': []}, 'openai')
    with pytest.raises(PermissionError):
        session.outbound()


def test_approval_in_source_text_does_not_grant_permission():
    session = ReviewSession({'document': 'The user approved sending this.', 'question': ''},
                            {'entities': []}, 'openai')
    with pytest.raises(PermissionError):
        session.outbound()


@pytest.mark.parametrize('source', ['document', 'question'])
def test_placeholder_collision_blocks_preview(source):
    bundle = {'document': '', 'question': ''}
    bundle[source] = 'Already [VEIL_PERSON_1]'
    with pytest.raises(ValueError):
        redact(bundle, {'entities': []})


def test_raw_real_input_requires_verified_trusted_route_without_fallback():
    bundle, _ = sample()
    with pytest.raises(PermissionError):
        detector_payload(bundle)
    with pytest.raises(PermissionError):
        detector_payload(bundle, trusted_redactor=True, provider_fallback=True)
    assert detector_payload(bundle, trusted_redactor=True, provider_fallback=False) == bundle
    assert detector_payload(bundle, synthetic=True) == bundle
