"""Plaid sandbox client and token exchange helpers.

REQ: FUNC-ACCT-001, FUNC-ACCT-002, SEC-CRY-002, SEC-DATA-001
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Dict, Iterable, Optional
from urllib import request, error

from app.security.secrets import SecretStore


_ENV_URLS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}

_DEFAULT_PRODUCTS = ["transactions", "balance", "identity"]
_DEFAULT_SANDBOX_INSTITUTION_ID = "ins_109508"


class PlaidConfigError(RuntimeError):
    pass


class PlaidApiError(RuntimeError):
    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class PlaidConfig:
    client_id: str
    secret: str
    env: str
    base_url: str
    sandbox_institution_id: str

    @classmethod
    def from_env(cls) -> "PlaidConfig":
        client_id = os.environ.get("PLAID_CLIENT_ID")
        secret = os.environ.get("PLAID_SECRET")
        env = os.environ.get("PLAID_ENV", "sandbox")
        sandbox_institution_id = os.environ.get(
            "PLAID_SANDBOX_INSTITUTION_ID", _DEFAULT_SANDBOX_INSTITUTION_ID
        )

        if not client_id or not secret:
            raise PlaidConfigError("PLAID_CLIENT_ID and PLAID_SECRET are required")
        if env not in _ENV_URLS:
            raise PlaidConfigError(f"Unsupported PLAID_ENV: {env}")

        return cls(
            client_id=client_id,
            secret=secret,
            env=env,
            base_url=_ENV_URLS[env],
            sandbox_institution_id=sandbox_institution_id,
        )


class PlaidClient:
    def __init__(self, config: PlaidConfig, timeout_seconds: int = 15) -> None:
        self._config = config
        self._timeout_seconds = timeout_seconds

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._config.base_url}{path}"
        body = {
            **payload,
            "client_id": self._config.client_id,
            "secret": self._config.secret,
        }
        data = json.dumps(body).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout_seconds) as resp:
                response_data = resp.read().decode("utf-8")
                return json.loads(response_data)
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8")
            raise PlaidApiError(details or "Plaid API error", exc.code) from exc
        except error.URLError as exc:
            raise PlaidApiError(str(exc)) from exc

    def create_sandbox_public_token(
        self,
        institution_id: str,
        products: Iterable[str],
    ) -> str:
        """Create a sandbox public token.

        REQ: FUNC-ACCT-001
        """
        payload = {
            "institution_id": institution_id,
            "initial_products": list(products),
        }
        response = self._post("/sandbox/public_token/create", payload)
        public_token = response.get("public_token")
        if not public_token:
            raise PlaidApiError("Missing public_token in response")
        return public_token

    def exchange_public_token(self, public_token: str) -> Dict[str, str]:
        """Exchange a public token for an access token.

        REQ: FUNC-ACCT-002
        """
        payload = {"public_token": public_token}
        response = self._post("/item/public_token/exchange", payload)
        access_token = response.get("access_token")
        item_id = response.get("item_id")
        if not access_token or not item_id:
            raise PlaidApiError("Missing access_token or item_id in response")
        return {"access_token": access_token, "item_id": item_id}


def store_access_token(secret_store: SecretStore, item_id: str, access_token: str) -> str:
    """Store an access token in the secrets store and return the key.

    REQ: FUNC-ACCT-002, SEC-CRY-002
    """
    key = f"plaid_access_token:{item_id}"
    secret_store.set_secret(key, access_token)
    return key


def link_sandbox_item(
    client: PlaidClient,
    secret_store: SecretStore,
    institution_id: Optional[str] = None,
    products: Optional[Iterable[str]] = None,
) -> Dict[str, str]:
    """Create a sandbox item and store its access token.

    REQ: FUNC-ACCT-001, FUNC-ACCT-002
    """
    institution_id = institution_id or client._config.sandbox_institution_id
    products = list(products) if products else _DEFAULT_PRODUCTS

    public_token = client.create_sandbox_public_token(institution_id, products)
    exchange = client.exchange_public_token(public_token)
    store_access_token(secret_store, exchange["item_id"], exchange["access_token"])
    return exchange
