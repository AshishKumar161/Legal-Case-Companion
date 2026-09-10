# Phase XX: AI Cost, Capacity Controls & Multilingual Safety

## Overview
LCC enforces strict operational and financial safety bounds on AI research capabilities to prevent cost overruns, model exhaustion, or unsafe degradation.

## Multilingual Safety Controls
- **Devanagari Prompt Injection Defense**: Neutralizes instruction override attempts in native Hindi script (`पिछले सभी निर्देश भूल जाओ`, `सिस्टम निर्देश ओवरराइड`).
- **Transliterated Hindi Defense**: Neutralizes Latin-script phonetic injection patterns (`kripya purv nirdesh bhul jao`, `system prompt override karo`).
- **Zero Hallucination Invariant**: Enforces empty-retrieval refusal behavior across all supported languages (`Evidence insufficient. The system cannot reliably answer this point from the available sources.`).
- **Statutory Temporal Grounding**: Accurately validates historical transition from IPC 1860 / CrPC 1973 to Bharatiya Nyaya Sanhita (BNS) 2023 / BNSS 2023 across English, Hindi, and Hinglish queries.

## Cost & Capacity Limits
1. **Daily User Quotas**: Default ceiling of 50 research queries and 100,000 tokens per user per day.
2. **Circuit Breaker & Emergency Disablement**: Immediate platform-wide AI disablement via `PILOT_DISABLED_FEATURES = ["ai"]` without taking down core case management or consultations.
3. **Graceful Degradation**: If external LLM providers experience latency spikes (>15s) or HTTP 5xx errors, queries fail closed with transparent informational notices rather than routing to unvetted fallback models.
