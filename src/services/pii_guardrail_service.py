import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class MaskingSession:
    """Session holding bidirectional mappings between real PII / UUIDs and anonymized tokens."""
    uuid_to_token: dict[str, str] = field(default_factory=dict)
    token_to_uuid: dict[str, str] = field(default_factory=dict)
    name_to_token: dict[str, str] = field(default_factory=dict)
    token_to_name: dict[str, str] = field(default_factory=dict)
    pii_to_token: dict[str, str] = field(default_factory=dict)
    token_to_pii: dict[str, str] = field(default_factory=dict)

    asset_counter: int = 0
    credit_counter: int = 0
    name_counter: int = 0
    phone_counter: int = 0
    card_counter: int = 0
    iin_counter: int = 0


class PIIGuardrailService:
    CARD_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")
    IIN_REGEX = re.compile(r"\b\d{12}\b")
    PHONE_REGEX = re.compile(
        r"(?:\+?7|8)[\s\-]?(?:\(?7\d{2}\)?|\(?\d{3}\)?)[ \-]?\d{3}[ \-]?\d{2}[ \-]?\d{2}\b"
    )

    @classmethod
    def create_session(cls) -> MaskingSession:
        return MaskingSession()

    @classmethod
    def mask_assets_context(
        cls,
        assets: list[dict[str, Any]] | None,
        session: MaskingSession
    ) -> list[dict[str, Any]]:
        if not assets:
            return []
        masked_assets = []
        for a in assets:
            real_id = str(a.get("id"))
            real_name = str(a.get("name", "")).strip()

            if real_id not in session.uuid_to_token:
                session.asset_counter += 1
                token = f"[СЧЕТ_{session.asset_counter}]"
                session.uuid_to_token[real_id] = token
                session.token_to_uuid[token] = real_id
                if real_name:
                    session.name_to_token[real_name.lower()] = token
                    session.token_to_name[token] = real_name
            else:
                token = session.uuid_to_token[real_id]

            masked_assets.append({
                "id": token,
                "name": token,
                "type": a.get("type"),
                "currency": a.get("currency")
            })
        return masked_assets

    @classmethod
    def mask_credits_context(
        cls,
        credits_ctx: list[dict[str, Any]] | None,
        session: MaskingSession
    ) -> list[dict[str, Any]]:
        if not credits_ctx:
            return []
        masked_credits = []
        for c in credits_ctx:
            real_id = str(c.get("id"))
            real_name = str(c.get("name", "")).strip()

            if real_id not in session.uuid_to_token:
                session.credit_counter += 1
                token = f"[КРЕДИТ_{session.credit_counter}]"
                session.uuid_to_token[real_id] = token
                session.token_to_uuid[token] = real_id
                if real_name:
                    session.name_to_token[real_name.lower()] = token
                    session.token_to_name[token] = real_name
            else:
                token = session.uuid_to_token[real_id]

            masked_credits.append({
                "id": token,
                "name": token,
                "remaining_amount": c.get("remaining_amount"),
                "monthly_payment": c.get("monthly_payment"),
                "currency": c.get("currency")
            })
        return masked_credits

    @classmethod
    def mask_text(
        cls,
        text: str,
        session: MaskingSession,
        known_names: list[str] | None = None
    ) -> str:
        if not text:
            return text

        masked = text

        # 1. Mask card numbers
        def _card_sub(m: re.Match) -> str:
            val = m.group(0)
            if val not in session.pii_to_token:
                session.card_counter += 1
                tok = f"[КАРТА_{session.card_counter}]"
                session.pii_to_token[val] = tok
                session.token_to_pii[tok] = val
            return session.pii_to_token[val]

        masked = cls.CARD_REGEX.sub(_card_sub, masked)

        # 2. Mask IIN (12 digits)
        def _iin_sub(m: re.Match) -> str:
            val = m.group(0)
            if val not in session.pii_to_token:
                session.iin_counter += 1
                tok = f"[ИИН_{session.iin_counter}]"
                session.pii_to_token[val] = tok
                session.token_to_pii[tok] = val
            return session.pii_to_token[val]

        masked = cls.IIN_REGEX.sub(_iin_sub, masked)

        # 3. Mask phone numbers
        def _phone_sub(m: re.Match) -> str:
            val = m.group(0)
            if val not in session.pii_to_token:
                session.phone_counter += 1
                tok = f"[ТЕЛЕФОН_{session.phone_counter}]"
                session.pii_to_token[val] = tok
                session.token_to_pii[tok] = val
            return session.pii_to_token[val]

        masked = cls.PHONE_REGEX.sub(_phone_sub, masked)

        # 4. Mask known account & credit names in text
        # Sort by length descending to replace longer names first
        sorted_names = sorted(session.name_to_token.keys(), key=len, reverse=True)
        for real_name_lower in sorted_names:
            if len(real_name_lower) >= 3:
                token = session.name_to_token[real_name_lower]
                pattern = re.compile(re.escape(real_name_lower), re.IGNORECASE)
                masked = pattern.sub(token, masked)

        # 5. Mask known person names
        if known_names:
            for name in known_names:
                clean_name = name.strip()
                if len(clean_name) >= 2:
                    if clean_name not in session.pii_to_token:
                        session.name_counter += 1
                        tok = f"[ИМЯ_{session.name_counter}]"
                        session.pii_to_token[clean_name] = tok
                        session.token_to_pii[tok] = clean_name
                    tok = session.pii_to_token[clean_name]
                    pattern = re.compile(r"\b" + re.escape(clean_name) + r"[а-яА-Я]*\b", re.IGNORECASE)
                    masked = pattern.sub(tok, masked)

        return masked

    @classmethod
    def unmask_payload(cls, payload: dict[str, Any], session: MaskingSession) -> dict[str, Any]:
        """Restores real UUIDs, asset/credit names, and unmasks PII tokens in payload."""
        items = payload.get("items", [])
        for it in items:
            # Asset unmask
            asset_hint = str(it.get("asset_account_id") or "")
            if asset_hint in session.token_to_uuid:
                it["asset_account_id"] = session.token_to_uuid[asset_hint]
            elif asset_hint in session.token_to_name:
                it["asset_account_id"] = session.token_to_uuid.get(asset_hint)

            target_asset = str(it.get("target_asset_name") or "")
            if target_asset in session.token_to_name:
                it["target_asset_name"] = session.token_to_name[target_asset]
                if not it.get("asset_account_id"):
                    it["asset_account_id"] = session.token_to_uuid.get(target_asset)

            # Credit unmask
            credit_hint = str(it.get("credit_account_id") or "")
            if credit_hint in session.token_to_uuid:
                it["credit_account_id"] = session.token_to_uuid[credit_hint]
            elif credit_hint in session.token_to_name:
                it["credit_account_id"] = session.token_to_uuid.get(credit_hint)

            target_credit = str(it.get("target_credit_name") or "")
            if target_credit in session.token_to_name:
                it["target_credit_name"] = session.token_to_name[target_credit]
                if not it.get("credit_account_id"):
                    it["credit_account_id"] = session.token_to_uuid.get(target_credit)

            # Restore PII and tokens in item_name and raw_text
            for field_name in ("item_name", "raw_text"):
                val = it.get(field_name)
                if val and isinstance(val, str):
                    for tok, orig in session.token_to_pii.items():
                        val = val.replace(tok, orig)
                    for tok, orig in session.token_to_name.items():
                        val = val.replace(tok, orig)
                    it[field_name] = val

        return payload
