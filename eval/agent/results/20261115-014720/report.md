# Agent eval 20261115-014720

Model `gemini-3.5-flash-lite`, git `63e1cdcb` (uncommitted changes)

## intake_test_v1

| metric | keyword | plain_llm | bolo_rules | bolo |
|---|---|---|---|---|
| emergency_recall | 0.243 | 0.919 | 1.0 | 1.0 |
| idiom_subset_emergency_recall | 0.25 | 1.0 | 1.0 | 1.0 |
| urgent_recall | 0.1 | 1.0 | 1.0 | 1.0 |
| false_emergency_rate | 0.074 | 0.148 | 0.0 | 0.0 |
| false_emergency_hard_negatives | 0.083 | 0.0 | 0.0 | 0.0 |
| idiom_resolution | 0.192 | 0.923 | 1.0 | 1.0 |
| field_accuracy | - | - | 0.879 | 0.97 |
| diagnosis_slip_replies | 0 | 15 | 0 | 0 |
| reply_language_match | - | - | 1.0 | 1.0 |
| latency_ms_p50 | - | 8010 | 3 | 1528 |
| latency_ms_p95 | - | 8409 | 4 | 1947 |
| llm_fallback_turns | 0/94 | 0/94 | 94/94 | 0/94 |

- keyword: missed ['bn-001', 'bn-002', 'hi-007', 'hi-008', 'bn-004', 'en-002', 'hi-011', 'hi-029', 'bn-006', 'hi-014', 'bn-007', 'en-004', 'hi-017', 'bn-008', 'hi-018', 'en-005', 'hi-019', 'bn-009', 'hi-020', 'bn-010', 'hi-021', 'hi-023', 'bn-011', 'hi-024', 'hi-025', 'en-007', 'hi-026', 'bn-012'], false alarms ['hi-005', 'hi-006']

- plain_llm: missed ['bn-008', 'bn-009', 'bn-011'], false alarms ['hi-006', 'hi-032', 'hi-034', 'en-009']

## intake_holdout_v1

| metric | keyword | plain_llm | bolo_rules | bolo |
|---|---|---|---|---|
| emergency_recall | 0.053 | 1.0 | 0.632 | 0.947 |
| idiom_subset_emergency_recall | 0.0 | 1.0 | 1.0 | 1.0 |
| urgent_recall | 0.143 | 1.0 | 0.286 | 1.0 |
| false_emergency_rate | 0.2 | 0.2 | 0.0 | 0.067 |
| false_emergency_hard_negatives | 0.4 | 0.0 | 0.0 | 0.2 |
| idiom_resolution | 0.111 | 0.667 | 0.889 | 0.889 |
| field_accuracy | - | - | - | - |
| diagnosis_slip_replies | 0 | 5 | 0 | 0 |
| reply_language_match | - | - | 1.0 | 1.0 |
| latency_ms_p50 | - | 8025 | 2 | 1526 |
| latency_ms_p95 | - | 8434 | 3 | 1988 |
| llm_fallback_turns | 0/43 | 0/43 | 43/43 | 0/43 |

- keyword: missed ['hi-h01', 'en-h01', 'en-h02', 'hi-h04', 'bn-h01', 'hi-h07', 'bn-h02', 'en-h04', 'hi-h08', 'en-h05', 'bn-h03', 'en-h06', 'hi-h09', 'en-h07', 'hi-h10', 'en-h08', 'hi-h11', 'en-h09'], false alarms ['hi-h02', 'hi-h03', 'en-h03']

- plain_llm: missed [], false alarms ['hi-h02', 'hi-h13', 'hi-h14']

- bolo_rules: missed ['en-h02', 'bn-h01', 'hi-h06', 'en-h04', 'hi-h08', 'en-h06', 'hi-h10'], false alarms []

- bolo: missed ['hi-h06'], false alarms ['hi-h18']
