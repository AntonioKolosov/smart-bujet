import re
from decimal import Decimal, InvalidOperation

CURRENCY_SUFFIXES = r"(?:руб(?:лей|ля|\.)?|р\b|тг\b|тенге|kzt\b|rub\b|usd\b|\$|€)"


class ParserService:
    @staticmethod
    def normalize_item_name(name: str) -> str:
        """Strip extra spaces and capitalize the first letter without mangling internal casing."""
        if not name:
            return ""
        cleaned = " ".join(name.strip().split())
        if not cleaned:
            return ""
        return cleaned[0].upper() + cleaned[1:]

    @staticmethod
    def parse_text(text: str) -> tuple[Decimal, str] | None:
        """
        Fast regex-based extraction of amount and item name from user message.
        Examples:
          '1000 яблоки' -> (Decimal('1000'), 'Яблоки')
          'яблоки 1500.50' -> (Decimal('1500.50'), 'Яблоки')
          'кофе 500 руб' -> (Decimal('500'), 'Кофе')
        """
        if not text:
            return None

        # If text mentions discount, bypass single-item regex to let AI process discount
        if re.search(r"(?:скидк|дисконт|акци|-%|off)", text, re.IGNORECASE):
            return None

        # If text mentions income, return of debt, transfer, deposit or currency keywords, bypass regex to let AI classify
        if re.search(
            r"(?:зарплат|доход|аванс|преми|подар|пополн|перевод|перевел|перевела|скинул|скинула|отправил|"
            r"вернул|вернула|вернули|возврат|отдал|отдала|отдали|долг|получ|получил|получила|"
            r"пришл|пришли|пришел|депозит|вклад|копилк|валют|доллар|\$|евро|€|брокер|кредит|рассрочк|платеж)",
            text,
            re.IGNORECASE,
        ):
            return None

        # If multiple numbers exist, bypass single-item regex to let AI process multi-item batch
        numbers = re.findall(r"\b\d+(?:[.,]\d+)?\b", text)
        if len(numbers) > 1:
            return None

        # Pattern 1: Number at start -> "1000 яблоки" or "1000.50 руб яблоки"
        m1 = re.match(
            rf"^\s*([0-9]+(?:[.,][0-9]{{1,2}})?)\s*{CURRENCY_SUFFIXES}?\s*(.*)$",
            text,
            flags=re.IGNORECASE
        )
        if m1 and m1.group(2).strip():
            amt_str = m1.group(1).replace(",", ".")
            desc = re.sub(CURRENCY_SUFFIXES, "", m1.group(2), flags=re.IGNORECASE).strip()
            try:
                amt = Decimal(amt_str)
                if amt > 0 and desc:
                    return amt, ParserService.normalize_item_name(desc)
            except InvalidOperation:
                pass

        # Pattern 2: Number at end -> "яблоки 1000" or "яблоки 1000 руб"
        m2 = re.match(
            rf"^(.*?)\s+([0-9]+(?:[.,][0-9]{{1,2}})?)\s*{CURRENCY_SUFFIXES}?\s*$",
            text,
            flags=re.IGNORECASE
        )
        if m2 and m2.group(1).strip():
            amt_str = m2.group(2).replace(",", ".")
            desc = re.sub(CURRENCY_SUFFIXES, "", m2.group(1), flags=re.IGNORECASE).strip()
            try:
                amt = Decimal(amt_str)
                if amt > 0 and desc:
                    return amt, ParserService.normalize_item_name(desc)
            except InvalidOperation:
                pass

        # Fallback: Find first isolated number anywhere in text
        match = re.search(r"\b([0-9]+(?:[.,][0-9]{1,2})?)\b", text)
        if match:
            amt_str = match.group(1).replace(",", ".")
            desc = text[:match.start()] + " " + text[match.end():]
            desc = re.sub(CURRENCY_SUFFIXES, "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"\s+", " ", desc).strip()
            try:
                amt = Decimal(amt_str)
                if amt > 0 and desc:
                    return amt, ParserService.normalize_item_name(desc)
            except InvalidOperation:
                pass

        return None

