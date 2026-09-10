# Phase XX: Advocate & Lawyer Professional Verification Maturity

## Overview
LCC enforces compliance with the Advocates Act, 1961 and Bar Council of India (BCI) rules. Unverified users can never appear in public discovery or accept legal consultations.

## Verification Lifecycle
1. **Submission**: Advocate provides State Bar Council enrollment number (`STATE/NUMBER/YEAR`), Bar Council body, and encrypted Bar ID document uploaded to Evidence Locker.
2. **Review**: Administrative / compliance officer validates against official Bar Council registers.
3. **Approval & Expiration**: Verifications are approved with an explicit expiration date (`expires_at`, default 365 days).
4. **Structured Rejection Taxonomy**:
   - `INVALID_ENROLLMENT_FORMAT`: Enrollment number fails statutory regex.
   - `BAR_COUNCIL_MISMATCH`: Stated council disagrees with issued jurisdiction.
   - `DOCUMENTS_ILLEGIBLE`: Uploaded credential illegible or unauthenticated.
   - `DISCIPLINARY_SANCTION`: Disciplinary suspension recorded by Bar Council.
   - `EXPIRED_CREDENTIALS`: Elapsed renewal date without re-verification.
5. **Immediate Revocation**: Upon verification lapse or revocation, advocate profile visibility is immediately suppressed and active availability disabled.
