"""Single source of truth for *who* bills an account.

DeployUnit sells two ways and an account must belong to exactly one of them:

  - "self"  → the customer signed up on deployunit.com and pays via Mollie
              inside the DeployUnit UI (checkout, subscription, cancel).
  - "whmcs" → the customer ordered through ServUnit/WHMCS; WHMCS owns the
              plan, invoices and dunning. The DeployUnit billing UI must be
              read-only for them, and Mollie must never be touched.

`users.billing_managed_by` is set to "whmcs" by the internal provisioning
API; anything else (unset included) means self-billing.
"""

from fastapi import HTTPException

WHMCS = "whmcs"
SELF = "self"


def billing_source(user: dict) -> str:
    return WHMCS if (user or {}).get("billing_managed_by") == WHMCS else SELF


def is_externally_billed(user: dict) -> bool:
    return billing_source(user) == WHMCS


def assert_self_billed(user: dict) -> None:
    """Reject any in-app billing mutation for externally-billed accounts."""
    if is_externally_billed(user):
        raise HTTPException(
            status_code=409,
            detail="This account is billed through ServUnit. Manage your plan and invoices there.",
        )
