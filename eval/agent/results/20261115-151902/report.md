# Agent eval 20261115-151902

Model `gemini-3.5-flash-lite`, git `d455abe2` (uncommitted changes)

## intake_test_v1

| metric | bolo | plain_llm |
|---|---|---|
| emergency_recall | 1.0 | 0.919 |
| emergency_any_flag | 1.0 | 1.0 |
| false_any_flag_rate | 0.176 | 0.588 |
| idiom_subset_emergency_recall | 1.0 | 0.917 |
| urgent_recall | 1.0 | 1.0 |
| false_emergency_rate | 0.0 | 0.148 |
| false_emergency_hard_negatives | 0.0 | 0.083 |
| idiom_resolution | 1.0 | 0.846 |
| field_accuracy | 0.939 | - |
| diagnosis_slip_replies | 0 | 10 |
| reply_language_match | 1.0 | - |
| latency_ms_p50 | 3154 | 9110 |
| latency_ms_p95 | 6334 | 24238 |
| llm_fallback_turns | 10/94 | 0/94 |

- plain_llm: missed ['hi-008', 'en-004', 'bn-008'], false alarms ['hi-006', 'hi-028', 'hi-034', 'en-009']

## intake_holdout_v1

| metric | bolo | plain_llm |
|---|---|---|
| emergency_recall | 0.895 | 0.947 |
| emergency_any_flag | 0.895 | 1.0 |
| false_any_flag_rate | 0.125 | 0.875 |
| idiom_subset_emergency_recall | 1.0 | 1.0 |
| urgent_recall | 1.0 | 1.0 |
| false_emergency_rate | 0.0 | 0.2 |
| false_emergency_hard_negatives | 0.0 | 0.0 |
| idiom_resolution | 1.0 | 0.889 |
| field_accuracy | - | - |
| diagnosis_slip_replies | 0 | 5 |
| reply_language_match | 1.0 | - |
| latency_ms_p50 | 2198 | 7884 |
| latency_ms_p95 | 7741 | 11969 |
| llm_fallback_turns | 6/43 | 0/43 |

- bolo: missed ['en-h02', 'bn-h01'], false alarms []

- plain_llm: missed ['bn-h03'], false alarms ['hi-h02', 'hi-h14', 'bn-h05']
