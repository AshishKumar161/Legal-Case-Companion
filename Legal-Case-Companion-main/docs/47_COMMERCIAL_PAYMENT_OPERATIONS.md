# Phase XX: Commercial Payment Operations & Tax Accounting

## Overview
LCC decouples commercial payment processing from consultation lifecycle state machines to prevent financial inconsistency, double spending, or state corruption during payment gateway outages.

## State Decoupling Architecture
- **Payment Lifecycle**: `PENDING` $\to$ `AUTHORIZED` $\to$ `CAPTURED` $\to$ `REFUNDED` / `PARTIALLY_REFUNDED` / `DISPUTED` / `CANCELLED`.
- **Consultation Lifecycle**: `REQUESTED` $\to$ `ACCEPTED` $\to$ `PAID` $\to$ `IN_PROGRESS` $\to$ `COMPLETED` / `CANCELLED`.
- **Entitlement Lifecycle**: `CommercialEntitlement` records active consultation minutes or credits. Entitlements are created only upon verified `CAPTURED` status and immediately revoked upon refund.

## Tax & Financial Record Handling
- **GST Regime**: Standard 18.0% Goods and Services Tax applied exclusively to the technology platform facilitation fee under Service Accounting Code (SAC) **9982** (Legal and Accounting Support Services).
- **Invoice Numbering**: Sequential non-colliding invoice numbering: `INV-YYYYMMDD-XXXX`.
- **Payment Reconciliation**: Cryptographic webhook signature verification (Stripe / Razorpay) ensures zero client-side manipulation of payment status.
