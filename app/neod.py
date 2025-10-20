from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional

import base58
from flask import current_app
from requests import HTTPError
from solana.exceptions import SolanaRpcException
from solana.keypair import Keypair
from solana.publickey import PublicKey
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from spl.token.client import Token
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import get_associated_token_address
from sqlalchemy.exc import IntegrityError

from .database import db
from .models import NeodMint, NeodPurchase

LAMPORTS_PER_SOL = 1_000_000_000
DEFAULT_RPC_URL = "https://api.mainnet-beta.solana.com"


class NeodServiceError(Exception):
    """Base error class for NEOD token operations."""


class ServiceConfigurationError(NeodServiceError):
    """Raised when mandatory configuration is missing."""


class PaymentAlreadyProcessed(NeodServiceError):
    """Raised when a SOL transfer signature has already been redeemed."""


class PaymentNotFound(NeodServiceError):
    """Raised when a referenced SOL transfer cannot be located on-chain."""


class PaymentVerificationError(NeodServiceError):
    """Raised when a SOL payment fails validation."""


class RecipientAccountError(NeodServiceError):
    """Raised when we cannot mint or transfer NEOD to the requested recipient."""


def _extract_signature(response) -> str:
    """Return a transaction signature string from an RPC response."""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        result = response.get("result")
        if isinstance(result, str):
            return result
    raise ValueError("Missing transaction signature in RPC response.")


@dataclass
class PaymentRecord:
    signature: str
    payer: str
    lamports: int
    slot: Optional[int]


def init_neod_service(app) -> Optional["NeodService"]:
    """Initialise and register the NEOD token service if credentials are present."""
    private_key = app.config.get("SOLANA_PRIVATE_KEY")
    wallet_address = app.config.get("SOLANA_WALLET_ADDRESS")
    if not private_key or not wallet_address:
        app.logger.info(
            "NEOD token service not configured; missing SOLANA_WALLET_ADDRESS or SOLANA_PRIVATE_KEY."
        )
        return None
    service = NeodService(app)
    app.extensions["neod_service"] = service
    return service


def get_neod_service(app=None) -> "NeodService":
    """Fetch the shared NEOD token service instance for the current app."""
    app = app or current_app
    service = app.extensions.get("neod_service")
    if not service:
        raise ServiceConfigurationError(
            "NEOD token service is not enabled; ensure SOLANA credentials are configured."
        )
    return service


def _normalise_pubkey(entry) -> str:
    """Return the base58 representation of a Solana account entry."""
    if isinstance(entry, dict):
        return entry.get("pubkey", "")
    if isinstance(entry, str):
        return entry
    return ""


def _parse_secret_key(raw: str) -> Keypair:
    """Parse a Solana keypair from common .env formats."""
    # Attempt JSON array of ints (solana-keygen format)
    try:
        data = json.loads(raw)
        if isinstance(data, list) and all(isinstance(item, int) for item in data):
            secret = bytes(data)
            return Keypair.from_secret_key(secret)
    except json.JSONDecodeError:
        pass

    # Attempt base58-encoded secret
    try:
        secret = base58.b58decode(raw)
        return Keypair.from_secret_key(secret)
    except ValueError as exc:
        raise ServiceConfigurationError("Invalid SOLANA_PRIVATE_KEY format") from exc


class NeodService:
    """Encapsulates the lifecycle of the NEOD utility token and purchase flow."""

    def __init__(self, app):
        self.app = app
        self.logger = app.logger.getChild("neod")
        self.rpc_url = app.config.get("SOLANA_RPC_URL", DEFAULT_RPC_URL)
        self.primary_rpc_url = self.rpc_url
        self.rpc_fallback_url = app.config.get("SOLANA_RPC_FALLBACK_URL", DEFAULT_RPC_URL) or DEFAULT_RPC_URL
        self.commitment = app.config.get("SOLANA_COMMITMENT", "confirmed")
        self.min_lamports = int(
            float(app.config.get("NEOD_MIN_SOL", "0.005")) * LAMPORTS_PER_SOL
        )
        self.neod_per_purchase = int(app.config.get("NEOD_TOKENS_PER_DONATION", "1"))
        self.initial_supply = int(app.config.get("NEOD_INITIAL_SUPPLY", "144000000"))
        self.decimals = int(app.config.get("NEOD_TOKEN_DECIMALS", "0"))

        self._keypair = _parse_secret_key(app.config["SOLANA_PRIVATE_KEY"])
        derived_address = str(self._keypair.public_key)
        configured_address = app.config.get("SOLANA_WALLET_ADDRESS")
        if configured_address and configured_address != derived_address:
            self.logger.warning(
                "Configured SOLANA_WALLET_ADDRESS (%s) does not match derived address (%s); using derived address.",
                configured_address,
                derived_address,
            )
        self.wallet_address = derived_address

        self.client = Client(self.rpc_url, commitment=self.commitment)
        self._token_client: Optional[Token] = None
        self._mint_pubkey: Optional[PublicKey] = None

    def _refresh_token_client(self) -> None:
        """Rebuild the Token client for the active RPC connection."""
        if self._mint_pubkey is None:
            self._token_client = None
            return
        self._token_client = Token(
            self.client,
            self._mint_pubkey,
            TOKEN_PROGRAM_ID,
            self._keypair,
        )

    def _switch_to_fallback(self, context: str) -> bool:
        """Swap to the fallback RPC endpoint if the primary becomes unavailable."""
        if not self.rpc_fallback_url or self.rpc_url == self.rpc_fallback_url:
            return False
        self.logger.warning(
            "RPC failure during %s on %s; switching to fallback endpoint %s",
            context,
            self.rpc_url,
            self.rpc_fallback_url,
        )
        self.rpc_url = self.rpc_fallback_url
        self.client = Client(self.rpc_url, commitment=self.commitment)
        self._refresh_token_client()
        return True

    def _should_retry_with_fallback(self, exc: Exception, context: str) -> bool:
        """Determine whether an RPC exception warrants retrying against the fallback."""
        if isinstance(exc, (SolanaRpcException, HTTPError)):
            return self._switch_to_fallback(context)
        return False

    # Public API -----------------------------------------------------------------
    def bootstrap(self) -> Optional[NeodMint]:
        """Ensure the NEOD mint exists and cache the Token client."""
        record = NeodMint.query.order_by(NeodMint.id.desc()).first()
        configured_mint = self.app.config.get("NEOD_MINT_ADDRESS")

        if configured_mint and (not record or record.mint_address != configured_mint):
            self.logger.info("Seeding NEOD mint record from configuration: %s", configured_mint)
            record = NeodMint(
                mint_address=configured_mint,
                authority_address=self.wallet_address,
                initial_supply=self.initial_supply,
                decimals=self.decimals,
            )
            db.session.add(record)
            db.session.commit()

        if record:
            self._mint_pubkey = PublicKey(record.mint_address)
            self._refresh_token_client()
            return record

        self.logger.info("No NEOD mint found; creating a fresh mint on %s", self.rpc_url)
        try:
            record = self._create_new_mint()
        except Exception as exc:
            self.logger.exception("Failed to create NEOD mint on Solana.")
            raise ServiceConfigurationError("Unable to create NEOD mint.") from exc
        return record

    def describe(self) -> dict:
        """Provide metadata about the NEOD token and treasury."""
        try:
            record = self.bootstrap()
        except NeodServiceError:
            raise
        except Exception as exc:
            raise ServiceConfigurationError("Failed to load NEOD mint details.") from exc
        token_client = self._ensure_token_client()
        source_account = self._get_or_create_associated_account(self._keypair.public_key)
        current_balance = 0
        try:
            source_details = token_client.get_account_info(source_account)
            current_balance = int(source_details.amount)
            self.logger.info("Treasury balance: %s NEOD tokens", current_balance)
        except Exception as exc:
            self.logger.warning("Failed to fetch treasury balance, defaulting to 0: %s", exc)
            # Try direct RPC call as fallback
            try:
                response = self.client.get_token_account_balance(source_account)
                if isinstance(response, dict) and 'result' in response:
                    balance_info = response['result'].get('value', {})
                    current_balance = int(balance_info.get('amount', 0))
                    self.logger.info("Treasury balance (via direct RPC): %s NEOD tokens", current_balance)
            except Exception as rpc_exc:
                self.logger.error("Direct RPC balance check also failed: %s", rpc_exc)

        tokens_per_unit = max(self.neod_per_purchase, 1)
        lamports_per_token = max(1, int(self.min_lamports / tokens_per_unit))
        sol_per_token = lamports_per_token / LAMPORTS_PER_SOL

        return {
            "mint_address": str(self._mint_pubkey),
            "treasury_wallet": self.wallet_address,
            "price_lamports": self.min_lamports,
            "price_sol": self.min_lamports / LAMPORTS_PER_SOL,
            "token_decimals": self.decimals,
            "tokens_per_purchase": self.neod_per_purchase,
            "lamports_per_token": lamports_per_token,
            "sol_per_token": sol_per_token,
            "initial_supply": record.initial_supply,
            "available_supply": current_balance,
            "rpc_url": self.rpc_url,
        }

    def fulfill_purchase(self, signature: str, recipient: str) -> NeodPurchase:
        """Validate an incoming SOL transfer and dispense NEOD to the recipient."""
        signature = signature.strip()
        recipient = recipient.strip()
        if not signature or not recipient:
            raise PaymentVerificationError("Signature and recipient are required.")

        try:
            PublicKey(recipient)
        except Exception as exc:
            raise RecipientAccountError("Recipient must be a valid Solana address.") from exc

        existing = NeodPurchase.query.filter_by(signature=signature).first()
        if existing:
            raise PaymentAlreadyProcessed(f"Signature {signature} already redeemed.")

        payment = self._verify_sol_payment(signature)
        token_amount = self._calculate_token_amount(payment.lamports)
        token_signature = self._disburse_neod(recipient, token_amount)

        record = NeodPurchase(
            signature=payment.signature,
            payer_address=payment.payer,
            recipient_address=recipient,
            sol_lamports=payment.lamports,
            neod_amount=token_amount,
            neod_transfer_signature=token_signature,
            slot=payment.slot,
        )
        db.session.add(record)
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise PaymentAlreadyProcessed(f"Signature {signature} already redeemed.") from exc
        self.logger.info(
            "Dispensed %s NEOD to %s for SOL deposit %s lamports (signature: %s)",
            token_amount,
            recipient,
            payment.lamports,
            signature,
        )
        return record

    # Internal helpers -----------------------------------------------------------
    def _ensure_token_client(self) -> Token:
        if self._mint_pubkey is None:
            raise ServiceConfigurationError("NEOD mint has not been initialised.")
        if self._token_client is None:
            self._refresh_token_client()
        if self._token_client is None:
            raise ServiceConfigurationError("NEOD token client could not be initialised.")
        return self._token_client

    def _get_or_create_associated_account(self, owner: PublicKey) -> PublicKey:
        attempts = 0
        while True:
            token_client = self._ensure_token_client()
            ata = get_associated_token_address(owner, self._mint_pubkey)
            try:
                token_client.get_account_info(ata)
                return ata
            except Exception as lookup_exc:
                if isinstance(lookup_exc, (SolanaRpcException, HTTPError)) and attempts < 3:
                    if self._should_retry_with_fallback(lookup_exc, "associated account lookup"):
                        attempts += 1
                        continue
                self.logger.info("Creating associated NEOD account for %s", owner)
                try:
                    token_client.create_associated_token_account(owner)
                    return ata
                except Exception as create_exc:
                    if isinstance(create_exc, (SolanaRpcException, HTTPError)) and attempts < 3:
                        if self._should_retry_with_fallback(create_exc, "associated account creation"):
                            attempts += 1
                            continue
                    raise RecipientAccountError("Failed to prepare token accounts.") from create_exc

    def _create_new_mint(self) -> NeodMint:
        token = Token.create_mint(
            self.client,
            self._keypair,
            self._keypair.public_key,
            self.decimals,
            program_id=TOKEN_PROGRAM_ID,
            freeze_authority=self._keypair.public_key,
            skip_confirmation=False,
        )
        mint_pubkey = token.pubkey
        self.logger.info("Created NEOD mint: %s", mint_pubkey)

        self._token_client = token
        self._mint_pubkey = mint_pubkey

        treasury_account = self._get_or_create_associated_account(self._keypair.public_key)
        self.logger.info("Treasury associated token account initialised at %s", treasury_account)

        tx_response = token.mint_to(
            dest=treasury_account,
            mint_authority=self._keypair,
            amount=self.initial_supply,
            opts=TxOpts(
                skip_confirmation=False,
                preflight_commitment=self.commitment,
                skip_preflight=False,
            ),
        )
        try:
            tx_sig = _extract_signature(tx_response)
        except ValueError as exc:
            raise ServiceConfigurationError("NEOD mint initialisation returned an unexpected RPC response.") from exc
        self.logger.info(
            "Minted initial NEOD supply (%s tokens) to treasury. Signature: %s",
            self.initial_supply,
            tx_sig,
        )

        self._token_client = token
        self._mint_pubkey = mint_pubkey
        self._refresh_token_client()

        record = NeodMint(
            mint_address=str(mint_pubkey),
            authority_address=self.wallet_address,
            initial_supply=self.initial_supply,
            decimals=self.decimals,
            last_signature=tx_sig,
        )
        db.session.add(record)
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise ServiceConfigurationError("A NEOD mint record already exists.") from exc
        self.app.config["NEOD_MINT_ADDRESS"] = str(mint_pubkey)
        return record

    def _verify_sol_payment(self, signature: str) -> PaymentRecord:
        attempts = 0
        while True:
            try:
                response = self.client.get_transaction(
                    signature,
                    commitment=self.commitment,
                    encoding="jsonParsed",
                    max_supported_transaction_version=0,
                )
            except Exception as exc:
                if isinstance(exc, (SolanaRpcException, HTTPError)) and attempts < 3:
                    if self._should_retry_with_fallback(exc, "payment verification"):
                        attempts += 1
                        continue
                raise ServiceConfigurationError("Unable to reach Solana RPC to verify payment.") from exc
            break

        result = response.get("result")
        if not result:
            raise PaymentNotFound(f"Transaction {signature} not found on-chain.")

        meta = result.get("meta") or {}
        if meta.get("err"):
            raise PaymentVerificationError(f"Transaction {signature} failed on-chain.")

        account_entries = result["transaction"]["message"]["accountKeys"]
        account_pubkeys = [_normalise_pubkey(entry) for entry in account_entries]

        try:
            wallet_index = account_pubkeys.index(self.wallet_address)
        except ValueError as exc:
            raise PaymentVerificationError("No funds were directed to the treasury wallet.") from exc

        pre_balances = meta.get("preBalances", [])
        post_balances = meta.get("postBalances", [])
        if wallet_index >= len(pre_balances) or wallet_index >= len(post_balances):
            raise PaymentVerificationError("Balance metadata missing for treasury wallet.")

        lamports_received = post_balances[wallet_index] - pre_balances[wallet_index]
        if lamports_received < self.min_lamports:
            raise PaymentVerificationError(
                f"Deposit below required minimum. Received {lamports_received} lamports."
            )

        payer = ""
        for entry in account_entries:
            if isinstance(entry, dict) and entry.get("signer"):
                payer = entry.get("pubkey", "")
                if payer:
                    break
        if not payer and account_pubkeys:
            payer = account_pubkeys[0]

        slot = result.get("slot")
        return PaymentRecord(signature=signature, payer=payer, lamports=lamports_received, slot=slot)

    def _calculate_token_amount(self, lamports: int) -> int:
        """Map the lamports transferred into NEOD tokens at the configured rate."""
        multiplier = lamports // self.min_lamports
        tokens = multiplier * self.neod_per_purchase
        if tokens <= 0:
            raise PaymentVerificationError(
                "Deposit did not meet the minimum exchange rate requirement."
            )
        return tokens

    def _disburse_neod(self, recipient: str, tokens: int) -> str:
        recipient_pubkey = PublicKey(recipient)
        attempts = 0
        while True:
            token_client = self._ensure_token_client()
            try:
                treasury_account = self._get_or_create_associated_account(self._keypair.public_key)
                recipient_account = self._get_or_create_associated_account(recipient_pubkey)
            except RecipientAccountError:
                raise
            except Exception as exc:
                if isinstance(exc, (SolanaRpcException, HTTPError)) and attempts < 3:
                    if self._should_retry_with_fallback(exc, "token account preparation"):
                        attempts += 1
                        continue
                raise RecipientAccountError("Failed to prepare token accounts.") from exc

            amount = tokens * (10 ** self.decimals)
            try:
                response = token_client.transfer(
                    source=treasury_account,
                    dest=recipient_account,
                    owner=self._keypair,
                    amount=amount,
                    opts=TxOpts(
                        skip_confirmation=False,
                        preflight_commitment=self.commitment,
                        skip_preflight=False,
                    ),
                )
            except Exception as exc:
                if isinstance(exc, (SolanaRpcException, HTTPError)) and attempts < 3:
                    if self._should_retry_with_fallback(exc, "NEOD transfer"):
                        attempts += 1
                        continue
                raise RecipientAccountError("Failed to transfer NEOD to recipient.") from exc

            try:
                return _extract_signature(response)
            except ValueError as exc:
                raise RecipientAccountError("Unexpected response when transferring NEOD.") from exc
