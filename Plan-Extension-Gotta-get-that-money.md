
# 🔥 Tell Him You Want This Architecture

Add a new section to the implementation plan:

---

## 🧠 Unified SaaS Entitlement Architecture

### Goal

Implement full subscription-based access control for the Aether Audio Stack (ASR, TTS, SAP) using:

* Stripe (billing state)
* Passport (OIDC + realm roles)
* FastAPI services (JWT validation + role enforcement)

The system must support:

* Pro subscription purchase
* Automatic role assignment
* Automatic role removal on cancel
* Centralized entitlement via realm role `pro_audio`

---

# 🧩 1. Identity Layer (Passport)

Add these requirements:

### Realm Role

* Use realm role: `pro_audio`
* Must be included in access token (`realm_access.roles`)
* All services rely on this role for authorization

### Clients

* All browser clients must be:

  * Public
  * PKCE required
  * Standard Flow enabled
  * No client secret

### Backend Admin Client

Create a confidential client:

`billing-service`

Used for:

* Assigning roles via Admin API

---

# 💳 2. Stripe Integration (Automated Only)

### Stripe Requirements

* Create product: `Aether Audio Pro`
* Create recurring monthly subscription ($29)

### Backend Must Implement:

#### Endpoint 1 — Create Checkout Session

```http
POST /billing/create-checkout-session
```

Inputs:

* user email
* user id

Returns:

* Stripe checkout URL

---

#### Endpoint 2 — Stripe Webhook

```http
POST /billing/webhook
```

Must verify:

* Stripe signature
* Event authenticity

Must handle:

```text
checkout.session.completed
customer.subscription.deleted
invoice.payment_failed
```

---

# 🔁 3. Role Mapping Logic

Webhook behavior:

### On `checkout.session.completed`

* Extract user email
* Lookup Passport user
* Assign realm role `pro_audio`

### On `customer.subscription.deleted`

* Lookup Passport user
* Remove realm role `pro_audio`

### On `invoice.payment_failed`

* Optional: mark user in warning state
* No immediate role removal unless subscription is canceled

---

# 🔐 4. JWT Validation in All Services

Each of:

* ASR
* TTS
* SAP - Lives at ~/Documents/ACOUSTIC_PERCEPTION/sap & frontend-2nd-version(sap is backend)

Must implement:

### JWKS validation from Passport

Validate:

* issuer
* audience
* signature
* expiration

### Role enforcement

Add dependency:

```python
require_pro_audio()
```

Logic:

```python
if "pro_audio" not in token["realm_access"]["roles"]:
    raise 403
```

Attach to all protected routes.

---

# 🧱 5. Separation Principle (Important)

Billing service:

* Only talks to Stripe + Passport

ASR/TTS/SAP:

* Only validate JWT
* Never talk to Stripe

Passport:

* Never talks to Stripe
* Only receives Admin API role updates

This keeps clean boundaries.

---

# 🖥 6. Optional But Recommended

Add:

`GET /billing/status`

Returns:

* subscription status
* tier
* renewal date

This is useful for dashboard UI.

---

# 🚀 7. End-to-End Test Plan

Add to implementation plan:

1. User logs in
2. No `pro_audio` role → access denied
3. User purchases subscription
4. Stripe webhook fires
5. Role assigned
6. User logs out/in
7. Access granted
8. Cancel subscription
9. Role removed
10. Access denied

That’s your full SaaS loop.

--- Ignore SAP - I have another workspace open and those agents can add the needed stripe stuff.

# ⚠️ Important Corrections

Tell him explicitly:

* Do not use local JWT secret anymore.
* All services must validate Passport-issued tokens only.
* Role must be realm-level, not client-level.

---



