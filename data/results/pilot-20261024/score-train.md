# T1 score: train

- Chunks scored: 10 of 10 (failed: 0, no result yet: 0)
- Key entities: 278; recall 84.9% (type must match), detection 88.1% (any type), character coverage 85.3%
- Predicted spans: 246; precision 98.0%; over-redaction 2 (0.8%)
- Leak rate: 11.9% (33 key values appear verbatim in the output)
- Documents with zero leaks: 2 of 9 fully scored (9 with any result)
- Outputs that changed text outside placeholders: 6
- Placeholder numbering consistent (information only): 4 of 10 chunks

| Type | Key | Recall | Predicted | Precision | Leaked |
|---|---:|---:|---:|---:|---:|
| PERSON | 107 | 91.6% | 98 | 100.0% | 8 |
| ADDRESS | 38 | 73.7% | 36 | 91.7% | 6 |
| POSTCODE | 25 | 84.0% | 22 | 95.5% | 0 |
| EMAIL | 43 | 93.0% | 40 | 100.0% | 3 |
| PHONE | 30 | 100.0% | 30 | 100.0% | 0 |
| BANK_ACCOUNT | 6 | 66.7% | 4 | 100.0% | 2 |
| SORT_CODE | 2 | 100.0% | 2 | 100.0% | 0 |
| IBAN | 2 | 100.0% | 2 | 100.0% | 0 |
| CARD | 2 | 100.0% | 3 | 66.7% | 0 |
| NI_NUMBER | 1 | 100.0% | 1 | 100.0% | 0 |
| DOB | 2 | 100.0% | 2 | 100.0% | 0 |
| ID_DOC | 1 | 100.0% | 1 | 100.0% | 0 |
| CUSTOM | 19 | 26.3% | 5 | 100.0% | 14 |
| all | 278 | 84.9% | 246 | 98.0% | 33 |

## Leaks

- `correspondence-R1-f1-c000` CUSTOM: 'M/2018/284'
- `correspondence-R1-f1-c000` BANK_ACCOUNT: '6160'
- `correspondence-R1-f1-c000` CUSTOM: 'M/2018/284'
- `correspondence-R1-f1-c000` EMAIL: 'messaging.administration@enron.com'
- `insurance-INS1-f2-c000` ADDRESS: "Ivy Cottage, Queen's Place\nSwindon\nWiltshire"
- `insurance-INS1-f2-c000` ADDRESS: '100B Willow Street, SUNDERLAND, Tyne and Wear'
- `insurance-INS1-f2-c000` ADDRESS: "128 Queen's Place, Little Station, Cardiff, South Glamorgan"
- `insurance-INS1-f2-c000` ADDRESS: '164 Victoria Lane, NORWICH'
- `correspondence-R4-f1-c000` PERSON: 'NICHOLLS'
- `correspondence-R4-f1-c000` PERSON: 'Frank'
- `correspondence-R4-f1-c000` PERSON: 'AN'
- `correspondence-R4-f1-c000` PERSON: 'NICHOLLS'
- `correspondence-R4-f1-c000` PERSON: 'AW'
- `correspondence-R4-f1-c000` PERSON: 'AW'
- `correspondence-R4-f1-c000` CUSTOM: 'H8RN48'
- `correspondence-R4-f1-c000` CUSTOM: '406628252WGDVS'
- `correspondence-R4-f1-c000` CUSTOM: '31559767'
- `correspondence-R4-f1-c000` CUSTOM: 'MM7B7R'
- `correspondence-R4-f1-c000` CUSTOM: 'YBBM9D'
- `correspondence-R1-f2-c000` BANK_ACCOUNT: '0507'
- `correspondence-R1-f3-c000` CUSTOM: 'M/2020/471'
- `correspondence-R1-f3-c000` ADDRESS: 'Room 3.14'
- `correspondence-R1-f3-c000` CUSTOM: 'M/2020/471'
- `correspondence-R1-f3-c000` EMAIL: 'mail.admin@enron.com'
- `contracts-C1-f1-c030` PERSON: 'Elliott Thompson'
- `contracts-C1-f1-c030` PERSON: 'Elliott Thompson'
- `contracts-C1-f1-c030` ADDRESS: 'Flat 32B, 168 Church Avenue, Liverpool'
- `correspondence-R3-f3-c000` CUSTOM: 'M/2018/129'
- `correspondence-R3-f3-c000` CUSTOM: 'M/2018/129'
- `correspondence-R3-f3-c000` CUSTOM: 'M/2018/129'
- `correspondence-R3-f3-c000` CUSTOM: 'M/2018/129'
- `correspondence-R3-f3-c000` CUSTOM: 'CL-15593'
- `correspondence-R3-f3-c000` EMAIL: 'mail.admin@enron.com'

## Over-redactions that look like personal data (review: possibly a real value the key missed)

- `financial-gretel-train-19041-c000` as CARD: '**** **** **** 1234 (Last 4 digits)'

## Other over-redactions

- 1 x as POSTCODE: '[Postal Code]'

## Outputs that changed text outside placeholders

- `contracts-C1-f2-c028`: 21 chars, e.g. '’' became "'"
- `insurance-INS1-f2-c000`: 64 chars, e.g. '’' became "'"
- `contracts-C1-f1-c001`: 10 chars, e.g. '’' became "'"
- `correspondence-R1-f3-c000`: 1 chars, e.g. '214 Hope Street' became '[...]'
- `contracts-C1-f1-c030`: 4 chars, e.g. '’' became "'"
- `correspondence-R3-f3-c000`: 2 chars, e.g. '\n\n' became ''

## Malformed placeholders (tolerated)

None.

## Failed chunks

None.
