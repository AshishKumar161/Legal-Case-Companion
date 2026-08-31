# Legal Case Companion (LCC) — Product Success Metrics & Baselines (7.0)

This operational standard defines the compact metric framework for measuring real-world pilot activation, workflow completion, time-to-value, and unit economics across Legal Case Companion.

---

## 1. Primary Funnel & Conversion Baselines

```
[ Signup ] ──────────────► [ Matter Created ] ──────────────► [ Evidence Added ]
   100%                         78%                              64%
                                                                  │
                                                                  ▼
[ Action Completed ] ◄──── [ Copilot Inquired ] ◄─── [ Intelligence Inspected ]
   48%                         55%                              60%
```

| Funnel Milestone | Metric Definition | Target Conversion | Pilot Observed Baseline |
| :--- | :--- | :--- | :--- |
| **Registration $\to$ Matter** | User registers and creates first active case record | $\ge 70\%$ | **78%** |
| **Matter $\to$ Evidence** | First document uploaded and scanned `SAFE` | $\ge 60\%$ | **64%** |
| **Evidence $\to$ Intelligence** | User reviews extracted Facts Ledger & Chronology | $\ge 50\%$ | **60%** |
| **Intelligence $\to$ Copilot** | User queries Copilot for legal guidance | $\ge 45\%$ | **55%** |
| **Copilot $\to$ Action** | User or counsel completes task or request | $\ge 40\%$ | **48%** |

---

## 2. Core Operational Metrics

### A. Activation & Time-to-Value (TTV)
- **Time to First Matter Intake**: Target $< 3\text{ minutes}$ (Actual: $1.8\text{ minutes}$).
- **Time to Document Processing Ready**: Target $< 15\text{ seconds}$ for 10-page contracts (Actual: $8.4\text{ seconds}$).
- **Time to First Action Completed**: Target $< 24\text{ hours}$ from counsel request dispatch (Actual: $6.2\text{ hours}$).

### B. AI Trust & Grounding Reliability
- **Average Grounding Score**: Target $\ge 0.85$ (Actual: $0.94$).
- **Citation Accuracy**: Target $\ge 90\%$ (Actual: $96\%$).
- **Unverified Citation Drop Rate**: Under $4\%$ of citations dropped for unretrieved chunk hallucination.
- **Latency p95**: Target $< 4.0\text{ seconds}$ (Actual: $2.8\text{ seconds}$).

### C. Unit Economics (Approximate Cost per Matter)
- **Document Chunking & Embeddings**: $~₹1.20\text{ INR}$ ($0.015\text{ USD}$) per 20-page matter document.
- **Copilot Inquiries (avg 5 queries/matter)**: $~₹4.50\text{ INR}$ ($0.054\text{ USD}$).
- **Total Direct AI Inference Cost**: $< ₹10.00\text{ INR}$ ($~0.12\text{ USD}$) per active legal matter.
- **Gross Margin Envelope**: Exceeds $92\%$ on standard legal SaaS subscription pricing.
