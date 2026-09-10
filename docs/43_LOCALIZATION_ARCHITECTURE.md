# Phase XX: Internationalization & Localization Architecture

## Overview
The Legal Case Companion (LCC) implements a decoupled, first-class localization framework designed specifically for Indian legal-tech applications. It supports multi-locale message resolution without hardcoding translated strings inside business logic or user interface components.

## Supported Locales & Hierarchy
1. **Primary Locale**: `en-IN` (Indian English - Default)
2. **Regional Locale**: `hi-IN` (Hindi in Devanagari script)
3. **Extensibility**: Architected for additional Schedule VIII Indian languages (`bn-IN`, `ta-IN`, `te-IN`, `mr-IN`) through declarative JSON catalogs and database-backed translation governance.

```
Request / User Profile
       │
       ▼
Locale Resolution Engine (app/core/i18n.py)
   1. Explicit user profile account_locale
   2. Explicit query param (?locale=hi-IN)
   3. Accept-Language header parsing & quality weighting
   4. Fallback: en-IN
       │
       ▼
Translation Layer (app/services/translation_service.py)
   1. In-memory base dictionary (frontend/src/i18n/*.json)
   2. Database override layer (translation_messages where status = APPROVED)
   3. Fallback string if key missing
```

## Security & Architectural Constraints
- **Zero Localized Authorization**: Localized text strings are NEVER used as authorization keys, role identifiers, API enums, or database states. Machine identifiers remain strictly canonical ASCII (`CLIENT`, `LAWYER`, `ADMIN`, `CONFIRMED`, `CAPTURED`).
- **Translation Message Governance**:
  - `DRAFT`: Newly submitted translations.
  - `REVIEW`: In legal and linguistic QA.
  - `APPROVED`: Authoritative for production distribution.
  - `DEPRECATED`: Superseded translations.
- **Legal Translations**: Machine-generated translations for legal terms and statutory notices are explicitly marked non-authoritative until certified by human legal counsel.
