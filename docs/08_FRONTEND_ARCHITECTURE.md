# Frontend Architecture (Phase 5)

## Technology Stack
- **Framework:** Next.js (App Router)
- **Language:** TypeScript
- **Styling:** Vanilla CSS Modules with global CSS tokens
- **Data Fetching:** Custom `apiClient` wrapping the native `fetch` API.

## Project Structure
```
frontend/
├── src/
│   ├── api/
│   │   └── client.ts       # Typed fetch wrapper with token injection
│   ├── app/
│   │   ├── admin/          # Admin role protected routes
│   │   ├── cases/          # Client case management routes
│   │   ├── dashboard/      # Client unified entry dashboard
│   │   ├── lawyer/         # Lawyer role protected routes
│   │   ├── lawyers/        # Public lawyer discovery
│   │   ├── login/          # Auth - Login
│   │   ├── register/       # Auth - Registration
│   │   ├── globals.css     # Premium design tokens & base styles
│   │   └── layout.tsx      # Root layout wrapping AuthProvider
│   └── providers/
│       └── AuthProvider.tsx # Role-aware authentication context
```

## Route Structure & Authorization Behavior
The frontend utilizes a client-side boundary protection model acting as UX defense-in-depth, while relying absolutely on the FastAPI backend for authoritative security.

| Route | Authorized Roles | Fallback Action |
|-------|------------------|-----------------|
| `/` | Public | None |
| `/login`, `/register` | Public | None |
| `/dashboard` | `CLIENT` | Redirect to `/login`, `/lawyer/dashboard`, or `/admin/dashboard` based on role |
| `/cases/new`, `/cases/[id]` | `CLIENT` (Case participants) | Displays 403/404 via API error boundary |
| `/lawyer/dashboard`, `/lawyer/profile`| `LAWYER` | Redirect to `/dashboard` |
| `/admin/dashboard` | `ADMIN` | Redirect to `/dashboard` |

## API Integration Strategy
Instead of Redux or heavily cached global stores (e.g. React Query) which introduce overhead, the application uses local state initialized via `apiClient`.

`apiClient` features:
- Injects the `Authorization: Bearer <token>` from `localStorage` on authenticated routes.
- Proxies requests to the underlying FastAPI engine running on `http://127.0.0.1:8000`.
- Standardizes error extraction via `ApiError` mapping.
