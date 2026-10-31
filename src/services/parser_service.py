import re
from decimal import Decimal, InvalidOperation

CURRENCY_SUFFIXES = r"(?:руб(?:лей|ля|\.)?|р\b|тг\b|тенге|₸|kzt\b|rub\b|usd\b|\$|€)"
# Matches single number with optional 3-digit space-separated thousands (e.g. "15 000", "1 250 000.50") or plain digits
NUM_TOKEN_RE = r"(?:[1-9]\d{0,2}(?:[ \u00a0]\d{3})+|\d+)(?:[.,]\d{1,2})?"

# High-confidence deterministic expense category rules for <15ms local Fast-Path
_FAST_CATEGORY_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "Еда вне дома",
        re.compile(
            r"\b(?:кафе|кофейн[а-я]*|ресторан[а-я]*|столов[а-я]*|бургерн[а-я]*|пиццери[а-я]*|"
            r"старбакс|starbucks|coffee\s*boom|del\s*papa|додо|dodo|kfc|кфс|макдак|mcdonald|"
            r"burger\s*king|bahandi|баханди|бизнес[- ]ланч|доставка\s+еды|яндекс\s*еда|wolt|glovo)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Продукты",
        re.compile(
            r"\b(?:продукт[а-я]*|магнум|magnum|small|смолл|galmart|галмарт|арбуз|arbuz|"
            r"пятерочк[а-я]*|магнит|перекресток|вкусвилл|ашан|хлеб[а-я]*|молок[а-я]*|кефир|"
            r"сыр\b|мяс[а-я]*|куриц[а-я]*|говядин[а-я]*|рыб[а-я]*|яйц[а-я]*|овощ[а-я]*|"
            r"фрукт[а-я]*|яблок[а-я]*|банан[а-я]*|манты|пельмен[а-я]*|колбас[а-я]*|масло|"
            r"чай\b|кофе\b|вод[аыу]\b|сок\b|сладост[а-я]*|выпечк[а-я]*)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Транспорт",
        re.compile(
            r"\b(?:такси|яндекс\s*такси|yandex\s*go|убер|uber|indrive|индрайв|автобус|метро|"
            r"проезд[а-я]*|онай|onay|бензин|дизель|заправк[а-я]*|азс|парковк[а-я]*|автомойк[а-я]*|мойка\s+авто)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Здоровье",
        re.compile(
            r"\b(?:аптек[а-я]*|лекарств[а-я]*|таблетк[а-я]*|витамин[а-я]*|врач[а-я]*|"
            r"стоматолог[а-я]*|анализ[а-я]*|клиник[а-я]*|олимп|инвитро|invitro)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Обязательные расходы",
        re.compile(
            r"\b(?:коммуналк[а-я]*|ком\s*услуг[а-я]*|жкх|квартплат[а-я]*|интернет|мобильн[а-я]*\s+связь|"
            r"связь\b|тариф\b|электричеств[а-я]*|аренд[а-я]*\s+квартир[а-я]*)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Подписки",
        re.compile(
            r"\b(?:подписк[а-я]*|netflix|нетфликс|spotify|спотифай|youtube\s*premium|icloud|"
            r"яндекс\s*плюс|chatgpt|telegram\s*premium)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Ремонт",
        re.compile(
            r"\b(?:стройматериал[а-я]*|леруа|leroy|сантехник[а-я]*|шпаклевк[а-я]*|обои\b|"
            r"гвозд[а-я]*|шуруп[а-я]*|смесител[а-я]*|гофр[а-я]*)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Питомец",
        re.compile(
            r"\b(?:корм\s+для|зоомагазин[а-я]*|ветеринар[а-я]*|наполнитель\s+для)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Шоппинг",
        re.compile(
            r"\b(?:футболк[а-я]*|кроссовк[а-я]*|джинс[а-я]*|куртк[а-я]*|обув[а-я]*|одежд[а-я]*|"
            r"наушник[а-я]*|чехол\b)\b",
            re.IGNORECASE,
        ),
    ),
]


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
    def _parse_decimal(amt_raw: str) -> Decimal | None:
        cleaned = re.sub(r"[\s\u00a0]+", "", amt_raw).replace(",", ".")
        try:
            amt = Decimal(cleaned)
            return amt if amt > 0 else None
        except InvalidOperation:
            return None

    @staticmethod
    def guess_category(item_name: str) -> str | None:
        """
        High-precision deterministic category matcher for unambiguous everyday expenses.
        Returns canonical system category name or None if uncertain (delegating to Gemini).
        """
        if not item_name:
            return None
        for category_name, pattern in _FAST_CATEGORY_RULES:
            if pattern.search(item_name):
                return category_name
        return None

    @staticmethod
    def parse_text(text: str) -> tuple[Decimal, str] | None:
        """
        Fast regex-based extraction of amount and item name from user message.
        Supports space-separated thousands ('продукты 15 000' -> Decimal('15000'), 'Продукты').
        """
        if not text or "?" in text:
            return None

        # If text mentions discount, bypass single-item regex to let AI process discount
        if re.search(r"(?:скидк|дисконт|акци|-%|off)", text, re.IGNORECASE):
            return None

        # If text mentions income, debt, family transfer, deposit, credit, or currency keywords, bypass to AI
        if re.search(
            r"(?:зарплат|доход|аванс|преми|подар|кэшбэк|кешбэк|процент|дивиденд|подработк|стипенди|пенси|пособи|"
            r"пополн|перевод|перевел|перевела|скинул|скинула|отправил|продал|продала|"
            r"жене|мужу|супруг|партнер|половинк|"
            r"вернул|вернула|вернули|возврат|отдал|отдала|отдали|долг|получ|получил|получила|"
            r"пришл|пришли|пришел|депозит|вклад|копилк|валют|доллар|\$|евро|€|брокер|кредит|рассрочк|платеж)",
            text,
            re.IGNORECASE,
        ):
            return None

        # Must contain strictly 1 number token (treating '15 000' as a single number, but 'хлеб 300 молоко 600' as 2)
        numbers = re.findall(rf"(?<!\d){NUM_TOKEN_RE}(?!\d)", text)
        if len(numbers) != 1:
            return None

        # Pattern 1: Number at start -> "15 000 яблоки" or "1000.50 руб яблоки"
        m1 = re.match(
            rf"^\s*({NUM_TOKEN_RE})\s*{CURRENCY_SUFFIXES}?\s+(.+?)\s*$",
            text,
            flags=re.IGNORECASE
        )
        if m1 and m1.group(2).strip():
            amt = ParserService._parse_decimal(m1.group(1))
            desc = re.sub(CURRENCY_SUFFIXES, "", m1.group(2), flags=re.IGNORECASE).strip()
            if amt is not None and desc:
                return amt, ParserService.normalize_item_name(desc)

        # Pattern 2: Number at end -> "яблоки 15 000" or "яблоки 1000 руб"
        m2 = re.match(
            rf"^(.+?)\s+({NUM_TOKEN_RE})\s*{CURRENCY_SUFFIXES}?\s*$",
            text,
            flags=re.IGNORECASE
        )
        if m2 and m2.group(1).strip():
            amt = ParserService._parse_decimal(m2.group(2))
            desc = re.sub(CURRENCY_SUFFIXES, "", m2.group(1), flags=re.IGNORECASE).strip()
            if amt is not None and desc:
                return amt, ParserService.normalize_item_name(desc)

        # Fallback: Single isolated number anywhere in text
        match = re.search(rf"(?<!\d)({NUM_TOKEN_RE})(?!\d)", text)
        if match:
            amt = ParserService._parse_decimal(match.group(1))
            desc = text[:match.start()] + " " + text[match.end():]
            desc = re.sub(CURRENCY_SUFFIXES, "", desc, flags=re.IGNORECASE)
            desc = re.sub(r"\s+", " ", desc).strip()
            if amt is not None and desc:
                return amt, ParserService.normalize_item_name(desc)

        return None
