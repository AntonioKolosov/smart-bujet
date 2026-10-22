from __future__ import annotations

import asyncio
import gc
import io
import json
import logging
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.config import settings
from src.core.security import blind_index
from src.models.user import User
from src.models.alias import UserItemAlias
from src.models.transaction import Transaction, TransactionSource
from src.models.category import Category, CategoryType
from src.services.category_service import CategoryService
from src.services.transaction_service import TransactionService

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import pypdf
except ImportError:
    pypdf = None

logger = logging.getLogger(__name__)

CATEGORY_ALIASES: dict[str, str] = {
    "кафе и рестораны": "еда вне дома",
    "рестораны и кафе": "еда вне дома",
    "фастфуд": "еда вне дома",
    "коммунальные услуги": "обязательные расходы",
    "связь": "обязательные расходы",
    "интернет и связь": "обязательные расходы",
    "аренда": "обязательные расходы",
    "супермаркеты": "продукты",
    "аптека": "здоровье",
    "такси": "транспорт",
    "переводы": "денежный перевод",
}

INTERNAL_TRANSFER_RE = re.compile(
    r"(?:(?:на|с)\s+kaspi\s+депозит|пополнение\s+депозита|снятие\s+с\s+депозита|"
    r"перевод\s+между\s+своими\s+счетами|частичное\s+изъятие\s+вклада|"
    r"перевод\s+(?:на|со)\s+сво(?:й|его)\s+(?:депозит|вклад|счет))",
    re.IGNORECASE,
)

INCOME_KEYWORDS_RE = re.compile(
    r"(?:поступление|зачисление|пополнение|возврат|вознаграждение|кешбэк|кэшбэк|"
    r"бонус|зарплат|заработной\s+платы|приход|дивиденд|стипенди|пенси|пособи|"
    r"перевод\s+от|входящий\s+перевод)",
    re.IGNORECASE,
)

EXPENSE_KEYWORDS_RE = re.compile(
    r"(?:покупка|оплата|снятие|списание|перевод\s+на\s+другую\s+карту|"
    r"перевод\s+клиенту|исходящий\s+перевод|комиссия|платеж|погашение|банкомат|\batm\b)",
    re.IGNORECASE,
)

LOCAL_EXPENSE_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?:magnum|магнум|toimart|тоймарт|small|смолл|galmart|галмарт|arbuz|арбуз|"
            r"\bryadom\b|рядом|domashniy\s+biskvit|raxa\s+shop|istanbul\s+products|"
            r"супермаркет|supermarket|гастроном|минимаркет|продукты|пекарня|bakery|"
            r"carefood|вкусвилл|пятерочка|перекресток|магнит|лента|ашан|fix\s*price)",
            re.IGNORECASE,
        ),
        "Продукты",
    ),
    (
        re.compile(
            r"(?:kofeynya|кофейня|coffee|vanilla|cafe|кафе|restaurant|ресторан|"
            r"bistro|бистро|\bbar\b|бар|\bpub\b|паб|столовая|canteen|\bkfc\b|mcdonald|"
            r"burger|бургер|\bdodo\b|додо|pizza|пицц|sushi|суши|bahandi|salam\s*bro|"
            r"starbucks|zebra|del\s*papa|mamma\s*mia|\bwolt\b|\bglovo\b|яндекс\s*еда|"
            r"yandex\.eda|chocofood|kulikov|куликов)",
            re.IGNORECASE,
        ),
        "Еда вне дома",
    ),
    (
        re.compile(
            r"(?:onay|онай|\buber\b|yandex\.go|yandex\s+go|яндекс\s*такси|yandex\.taxi|"
            r"indriver|индрайвер|\bазс\b|\bazs\b|helios|гелиос|qazaq\s*oil|казакойл|"
            r"sinooil|синойл|compass|royal\s*petrol|газпромнефть|лукойл|парковка|"
            r"parking|aparking|avtobys|jet\s*sharing|whoosh|ктж|ktzh|air\s*astana|"
            r"flyarystan|\bscat\b)",
            re.IGNORECASE,
        ),
        "Транспорт",
    ),
    (
        re.compile(
            r"(?:apple\.com/bill|itunes|icloud|youtubepremium|youtube|google\s*\*|"
            r"netflix|spotify|yandex\s*plus|яндекс\s*плюс|kinopoisk|chatgpt|openai|"
            r"telegram|playstation|\bsteam\b|\bxbox\b|\bzoom\b|canva|patreon)",
            re.IGNORECASE,
        ),
        "Подписки",
    ),
    (
        re.compile(
            r"(?:tele2|теле2|altel|алтел|beeline|билайн|kcell|кселл|activ|актив|"
            r"казахтелеком|kazakhtelecom|алсеко|alseco|коммунал|ерц|еирц|\bкск\b|\bоси\b|"
            r"энергосбыт|водоканал|налог|штраф|госпошлин|правительство\s+для\s+граждан)",
            re.IGNORECASE,
        ),
        "Обязательные расходы",
    ),
    (
        re.compile(
            r"(?:аптека|apteka|pharmacy|rauze|рауза|europharma|еврофарма|биосфера|"
            r"садыхан|цветная|invivo|инвиво|олимп|\bkdl\b|клиника|медцентр|hospital|"
            r"dental|стоматолог|institut\s+reproduktivnoy|medical|оптика)",
            re.IGNORECASE,
        ),
        "Здоровье",
    ),
    (
        re.compile(
            r"(?:\bozon\b|озон|wildberries|вайлдберриз|kaspi\s*магазин|kaspi\.kz|"
            r"technodom|технодом|sulpak|сулпак|mechta|мечта|alser|белый\s+ветер|"
            r"flip\.kz|\bzara\b|bershka|massimo\s*dutti|waikiki|defacto|adidas|nike|"
            r"золотое\s+яблоко|gold\s*apple|mon\s*amie|французский\s+дом|beautymania|"
            r"детский\s+мир|marwin|меломан|ikea|leroy\s*merlin|леруа)",
            re.IGNORECASE,
        ),
        "Шоппинг",
    ),
    (
        re.compile(
            r"(?:строительн|стройматериал|12\s*месяцев|baumarkt|сантехник|обои)",
            re.IGNORECASE,
        ),
        "Ремонт",
    ),
    (
        re.compile(r"(?:зоомагазин|petshop|ветклиник|ветеринар|зоотовар)", re.IGNORECASE),
        "Питомец",
    ),
    (
        re.compile(
            r"(?:кинотеатр|chaplin|kinopark|кинопарк|lumiera|cinemax|ticketon|тикетon|"
            r"sxodim|боулинг|караоке|театр|концерт)",
            re.IGNORECASE,
        ),
        "Развлечения",
    ),
    (
        re.compile(
            r"(?:университет|колледж|школа|курсы|udemy|coursera|skillbox|практикум|обучение|детский\s+сад)",
            re.IGNORECASE,
        ),
        "Образование",
    ),
    (
        re.compile(
            r"(?:перевод\s+на\s+другую\s+карту|перевод\s+клиенту|перевод\s+с\s+карты|"
            r"перевод\s+по\s+номеру|\bp2p\b|перевод\s+\[имя_скрыто\]|^перевод$)",
            re.IGNORECASE,
        ),
        "Денежный перевод",
    ),
    (
        re.compile(
            r"(?:снятие\s+(?:денег|наличных)|банкомат|\batm\b|комиссия)",
            re.IGNORECASE,
        ),
        "Прочее",
    ),
]

LOCAL_INCOME_RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"(?:зарплат|заработной\s+платы|аванс|премия|стипенди|пенси|пособи|"
            r"мобайл\s+телеком\s*-\s*сервис|^тоо\s+|^ао\s+)",
            re.IGNORECASE,
        ),
        "Зарплата",
    ),
    (
        re.compile(
            r"(?:поступление\s+перевода|перевод\s+от|входящий\s+перевод|"
            r"пополнение\s+карты|перевод)",
            re.IGNORECASE,
        ),
        "Денежный перевод",
    ),
    (
        re.compile(r"(?:кешбэк|кэшбэк|бонус|вознаграждение|возврат)", re.IGNORECASE),
        "Прочее",
    ),
]


def _parse_money(raw_val: str | None) -> float | None:
    """Safely parse localized money strings like '- 3 200,00', '1,040,700.00', '3 389.00'."""
    if not raw_val:
        return None
    s = re.sub(r"[^\d.,+-]", "", str(raw_val).strip())
    if not s or s in ("+", "-", ".", ","):
        return None
    sign = -1.0 if s.startswith("-") else 1.0
    s = s.lstrip("+-")
    if "," in s and "." in s:
        if s.rfind(".") > s.rfind(","):
            s = s.replace(",", "")
        else:
            s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        parts = s.split(",")
        if len(parts[-1]) in (1, 2):
            s = "".join(parts[:-1]) + "." + parts[-1]
        else:
            s = "".join(parts)
    try:
        return round(sign * float(s), 2)
    except Exception:
        return None


def _parse_statement_date(date_str: str) -> str | None:
    """Convert DD.MM.YY or DD.MM.YYYY into ISO YYYY-MM-DD after validating calendar bounds."""
    m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4}|\d{2})$", date_str.strip())
    if not m:
        return None
    day, month, year_raw = int(m.group(1)), int(m.group(2)), m.group(3)
    year = (2000 + int(year_raw)) if len(year_raw) == 2 else int(year_raw)
    if not (1 <= month <= 12 and 1 <= day <= 31 and 2000 <= year <= 2035):
        return None
    try:
        dt = datetime(year, month, day)
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def clean_statement_merchant(raw_desc: str, tx_type: str = "expense") -> str:
    """Strip bank boilerplate, terminal codes, and city suffixes to deduplicate merchants cleanly."""
    s = " ".join((raw_desc or "").strip().split())
    if not s:
        return "Операция по выписке"

    # Strip leading operation type boilerplate from Halyk / Kaspi / Forte
    s = re.sub(
        r"^(?:Оплата\s+товаров\s+и\s+услуг|Безналичная\s+оплата(?:\s+товаров\s+и\s+услуг)?|"
        r"Покупка\s+товаров\s+и\s+услуг|Оплата\s+услуг|Списание\s+средств|"
        r"Зачисление\s+заработной\s+платы|Зачисление\s+средств|Поступление\s+средств|"
        r"Покупка|Оплата|Платеж|Разное)\s*[:\-]?\s*",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()

    if not s:
        return "Зарплата" if tx_type == "income" else "Покупка"

    # Strip trailing masked tokens, references, country/city codes
    s = re.sub(
        r"(?:\s+(?:\[CARD_MASKED\]|\[IBAN_MASKED\]|\[ID_MASKED\]|\*{4,}\d{4}))+.*$",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(
        r"\s+\b(?:ALMATY|ASTANA|NUR-SULTAN|SHYMKENT|KARAGANDA|ATYRAU|AKTOBE|PAVLODAR|"
        r"SEMEY|TARAZ|KOSTANAY|KYZYLORDA|URALSK|AKTAU|TURKESTAN|PETROPAVL|KOKSHETAU|"
        r"TALDYKORGAN|ZHEZKAZGAN|EKIBASTUZ|TEMIRTAU|KASKELEN|TALGAR|KONAYEV)\b(?:\s+\b(?:KZ|KAZ)\b)?\s*$",
        "",
        s,
        flags=re.IGNORECASE,
    ).strip()
    s = re.sub(r"\s+\b(?:KAZ|KZ|RUS|RU|USA|GBR|NLD|IRL|CYP|TUR|ARE|LUX)\b\s*$", "", s, flags=re.IGNORECASE).strip()

    # Collapse Magnum kassa/branch codes into unified 'Magnum'
    if re.search(r"\bMAGNUM\b", s, re.IGNORECASE) and not re.search(r"(?:ATM|БАНКОМАТ)", s, re.IGNORECASE):
        return "Magnum"

    # Collapse Yandex Go variations
    if re.search(r"\bYANDEX[\s.]*(?:GO|TAXI)\b", s, re.IGNORECASE):
        return "Yandex Go"

    return s[:200] or ("Зарплата" if tx_type == "income" else "Операция по выписке")


def match_local_category(item_name: str, tx_type: str) -> str | None:
    """Deterministic zero-token category matching for common Kazakhstan/CIS merchants."""
    rules = LOCAL_INCOME_RULES if tx_type == "income" else LOCAL_EXPENSE_RULES
    for pattern, category in rules:
        if pattern.search(item_name):
            return category
    return None


def extract_statement_metadata_regex(full_text: str) -> dict[str, Any]:
    """Deterministically extract bank_name, currency, period, and closing_balance from PDF text."""
    meta: dict[str, Any] = {
        "bank_name": None,
        "currency": None,
        "period_start": None,
        "period_end": None,
        "starting_balance": None,
        "closing_balance": None,
    }
    if not full_text:
        return meta

    header_before_tx = re.split(r"(?m)^\s*\d{2}\.\d{2}\.(?:\d{4}|\d{2})\b", full_text[:2500])[0].lower()
    lower_head = header_before_tx or full_text[:600].lower()
    if any(k in lower_head for k in ("народный банк", "halyk", "халык", "homebank")):
        meta["bank_name"] = "Halyk Bank"
    elif "kaspi" in lower_head:
        meta["bank_name"] = "Kaspi Bank"
    elif "forte" in lower_head:
        meta["bank_name"] = "ForteBank"
    elif "freedom" in lower_head or "фридом" in lower_head:
        meta["bank_name"] = "Freedom Bank"
    elif "центркредит" in lower_head or "bcc.kz" in lower_head:
        meta["bank_name"] = "Банк ЦентрКредит"
    elif "евразийский" in lower_head or "eurasian" in lower_head:
        meta["bank_name"] = "Евразийский Банк"
    elif "bereke" in lower_head or "береке" in lower_head:
        meta["bank_name"] = "Bereke Bank"
    elif "jusan" in lower_head or "жусан" in lower_head:
        meta["bank_name"] = "Jusan Bank"
    elif "сбербанк" in lower_head or "sber" in lower_head:
        meta["bank_name"] = "Сбербанк"
    elif any(k in lower_head for k in ("тинькофф", "т-банк", "tinkoff", "t-bank")):
        meta["bank_name"] = "Т-Банк"

    curr_m = re.search(
        r"(?:валюта(?:\s+счета|\s+карты)?|currency)\s*[:\-]?\s*\b(KZT|USD|EUR|RUB)\b",
        full_text[:6000],
        re.IGNORECASE,
    )
    if curr_m:
        meta["currency"] = curr_m.group(1).upper()
    elif "₸" in full_text[:6000] or "KZT" in full_text[:6000] or meta["bank_name"] in ("Kaspi Bank", "Halyk Bank", "ForteBank", "Банк ЦентрКредит"):
        meta["currency"] = "KZT"

    period_m = re.search(
        r"(?:за\s+период|период(?:\s+выписки)?)\s*[:\-]?\s*(?:с\s*)?(\d{2}\.\d{2}\.(?:\d{4}|\d{2}))"
        r"\s*(?:г\.?)?\s*(?:по|-|—|–)\s*(\d{2}\.\d{2}\.(?:\d{4}|\d{2}))",
        full_text[:6000],
        re.IGNORECASE,
    )
    if not period_m:
        period_m = re.search(
            r"\bс\s+(\d{2}\.\d{2}\.(?:\d{4}|\d{2}))\s*(?:г\.?)?\s*по\s+(\d{2}\.\d{2}\.(?:\d{4}|\d{2}))",
            full_text[:6000],
            re.IGNORECASE,
        )
    if period_m:
        meta["period_start"] = _parse_statement_date(period_m.group(1))
        meta["period_end"] = _parse_statement_date(period_m.group(2))

    # Search header and footer for closing_balance
    search_zones = [full_text[:5000]]
    if len(full_text) > 5000:
        search_zones.append(full_text[-5000:])
    combined_zone = "\n".join(search_zones)

    cb_patterns = [
        r"(?:Исходящий\s+остаток|Остаток\s+на\s+конец(?:\s+периода)?|Доступный\s+остаток|"
        r"Доступно(?:\s+на\s+\d{2}\.\d{2}\.(?:\d{4}|\d{2})(?:\s*г\.?)?)?|"
        r"Конечный\s+остаток|Остаток\s+средств\s+на\s+конец(?:\s+периода)?|"
        r"Шығыс\s+қалдық(?:\s*/\s*Исходящий\s+остаток)?)"
        r"\s*(?:на\s+\d{2}\.\d{2}\.(?:\d{4}|\d{2})(?:\s*г\.?)?)?\s*[:\-–—]?\s*"
        r"([+-]?\s*\d[\d\s\u00a0]*(?:[.,]\d{2}))\s*(?:₸|KZT|USD|EUR|RUB|тенге|руб)?",
    ]
    for pat in cb_patterns:
        matches = list(re.finditer(pat, combined_zone, re.IGNORECASE))
        if matches:
            val = _parse_money(matches[-1].group(1))
            if val is not None:
                meta["closing_balance"] = val
                break

    # Also check tabular summary header where 'Исходящий остаток' is at the end of a header line
    if meta["closing_balance"] is None:
        tab_m = re.search(
            r"(?:Входящий\s+остаток|Остаток\s+на\s+начало).*?(?:Исходящий\s+остаток|Остаток\s+на\s+конец[^\n]*)\n+"
            r"([^\n]*\d[\d\s\u00a0]*[.,]\d{2}[^\n]*)",
            combined_zone,
            re.IGNORECASE,
        )
        if tab_m:
            nums = re.findall(r"[+-]?\d[\d\s\u00a0]*[.,]\d{2}", tab_m.group(1))
            if len(nums) >= 2:
                val = _parse_money(nums[-1])
                if val is not None:
                    meta["closing_balance"] = val

    sb_m = re.search(
        r"(?:Входящий\s+остаток|Остаток\s+на\s+начало(?:\s+периода)?)"
        r"\s*(?:на\s+\d{2}\.\d{2}\.(?:\d{4}|\d{2})(?:\s*г\.?)?)?\s*[:\-–—]?\s*"
        r"([+-]?\s*\d[\d\s\u00a0]*(?:[.,]\d{2}))",
        combined_zone,
        re.IGNORECASE,
    )
    if sb_m:
        meta["starting_balance"] = _parse_money(sb_m.group(1))

    return meta


def extract_rows_locally(full_text: str) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Parse statement transaction rows locally via Regex (0 LLM tokens).
    Returns (parsed_rows, unparsed_candidate_blocks).
    Supports Kaspi Gold, Halyk Bank (single-column & 9-column), Forte, BCC, Sber, Tinkoff.
    """
    if not full_text:
        return [], []

    # Strip page markers and recurring table headers/footers
    cleaned = re.sub(r"(?m)^--- СТРАНИЦА \d+ ---\s*$", "", full_text)
    cleaned = re.sub(r"(?im)^\s*(?:Стр\.?|Страница)\s*\d+\s*(?:из|/)\s*\d+.*$", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*Дата\s+Сумма\s+Операция\s+Детали\s*$", "", cleaned)
    cleaned = re.sub(
        r"(?im)^\s*Дата\s+проведения.*?(?:Номер\s+карточки|Комиссия|Сумма\s+в\s+валюте).*$",
        "",
        cleaned,
    )

    # Join consecutive date-only lines (e.g. Halyk transaction date followed by processing date on next line)
    cleaned = re.sub(
        r"(?m)^(\s*\d{2}\.\d{2}\.(?:\d{4}|\d{2})(?:\s+\d{2}:\d{2}(?::\d{2})?)?)\s*\n+\s*(\d{2}\.\d{2}\.(?:\d{4}|\d{2})\b)",
        r"\1 \2",
        cleaned,
    )

    raw_blocks = re.split(r"(?m)(?=^\s*\d{2}\.\d{2}\.(?:\d{4}|\d{2})\b)", cleaned)
    parsed_rows: list[dict[str, Any]] = []
    unparsed_blocks: list[str] = []

    for block in raw_blocks:
        b = block.strip()
        if not b or not re.match(r"^\d{2}\.\d{2}\.(?:\d{4}|\d{2})\b", b):
            continue

        # Cut off trailing summary/footer lines that might be attached to the last transaction of a page
        b = re.split(
            r"(?im)^\s*(?:Итого(?:\s+по|\s+за|\s*:)|Всего\s+по|Исходящий\s+остаток|"
            r"Остаток\s+на\s+конец|Оборот\s+за|АО\s+[«\"'](?:Народный|Kaspi)|"
            r"Настоящая\s+выписка|Выписка\s+сформирована|Краткая\s+сводка)",
            b,
        )[0].strip()

        line = " ".join(b.split())
        m_head = re.match(
            r"^(?P<d1>\d{2}\.\d{2}\.(?:\d{4}|\d{2}))(?:\s+\d{2}:\d{2}(?::\d{2})?)?"
            r"(?:\s+(?P<d2>\d{2}\.\d{2}\.(?:\d{4}|\d{2}))(?:\s+\d{2}:\d{2}(?::\d{2})?)?)?"
            r"\s+(?P<rest>.+)$",
            line,
        )
        if not m_head:
            continue

        iso_date = _parse_statement_date(m_head.group("d1"))
        if not iso_date:
            continue

        rest = m_head.group("rest").strip()
        # Ignore period range headers like "14.01.2025 - 22.10.2026" or balance date headers
        if re.match(r"^(?:по|-|—|–)\s*\d{2}\.\d{2}\.", rest, re.IGNORECASE):
            continue
        if not re.search(r"\d", rest):
            continue

        # Skip internal deposit transfers
        if INTERNAL_TRANSFER_RE.search(rest):
            continue

        # Strip foreign currency equivalent in parentheses, e.g. "(- 10,00 $)"
        rest_clean = re.sub(
            r"\(\s*[-+]?\s*\d[\d\s\u00a0.,]*\s*(?:[$€₽₸]|[A-Z]{3})\s*\)",
            " ",
            rest,
        )
        # Strip trailing masked card/account tokens
        rest_clean = re.sub(
            r"(?:\s+(?:\[CARD_MASKED\]|\[IBAN_MASKED\]|\[ID_MASKED\]|\*{4,}\d{4}))+\s*$",
            "",
            rest_clean,
            flags=re.IGNORECASE,
        ).strip()
        rest_clean = " ".join(rest_clean.split())

        # Pattern 1: Kaspi / Tinkoff / Sber style — Signed amount immediately after date
        # e.g. "- 3 200,00 ₸ Покупка Magnum" or "+ 865 058,86 ₸ Пополнение ..."
        m_kaspi = re.match(
            r"^(?P<sign>[+-])\s*(?P<amt>\d[\d\s\u00a0]*(?:[.,]\d{1,2})?)\s*"
            r"(?:₸|KZT|USD|EUR|RUB|тенге|руб|\$|€|₽)?\s+"
            r"(?P<op>Покупка|Перевод|Пополнение|Снятие|Разное|Платеж|Оплата|Возврат|Вознаграждение|Кешбэк)?\s*"
            r"(?P<details>.*)$",
            rest_clean,
            re.IGNORECASE,
        )
        if m_kaspi:
            amt_val = _parse_money(m_kaspi.group("amt"))
            if amt_val is not None and abs(amt_val) > 0:
                tx_type = "income" if m_kaspi.group("sign") == "+" else "expense"
                raw_desc = (m_kaspi.group("details") or m_kaspi.group("op") or "").strip()
                item_name = clean_statement_merchant(raw_desc, tx_type)
                parsed_rows.append({
                    "date": iso_date,
                    "amount": round(abs(amt_val), 2),
                    "type": tx_type,
                    "item_name": item_name,
                })
                continue

        # Pattern 2: Halyk Bank Multi-Column style
        # "<Description> <op_amt> <CURR> <prihod> <rashod> [<fee>]"
        m_halyk_multi = re.match(
            r"^(?P<desc>.+?)\s+"
            r"(?P<op_amt>[+-]?\s*\d[\d\s\u00a0]*[.,]\d{2})\s+"
            r"(?P<curr>KZT|USD|EUR|RUB|GBP|CNY|TRY|AED|₸)\s+"
            r"(?P<prihod>[+-]?\s*\d[\d\s\u00a0]*[.,]\d{2})\s+"
            r"(?P<rashod>[+-]?\s*\d[\d\s\u00a0]*[.,]\d{2})"
            r"(?:\s+(?P<fee>[+-]?\s*\d[\d\s\u00a0]*[.,]\d{2}))?$",
            rest_clean,
            re.IGNORECASE,
        )
        if m_halyk_multi:
            desc = m_halyk_multi.group("desc").strip()
            p_val = _parse_money(m_halyk_multi.group("prihod")) or 0.0
            r_val = _parse_money(m_halyk_multi.group("rashod")) or 0.0
            f_val = _parse_money(m_halyk_multi.group("fee")) or 0.0
            op_val = _parse_money(m_halyk_multi.group("op_amt")) or 0.0

            amt_final = 0.0
            tx_type = "expense"
            if abs(p_val) > 0 and abs(r_val) == 0:
                amt_final = abs(p_val)
                tx_type = "income"
            elif abs(r_val) > 0 and abs(p_val) == 0:
                amt_final = round(abs(r_val) + abs(f_val), 2)
                tx_type = "expense"
            elif abs(op_val) > 0:
                amt_final = abs(op_val)
                if m_halyk_multi.group("op_amt").strip().startswith("-"):
                    tx_type = "expense"
                elif m_halyk_multi.group("op_amt").strip().startswith("+"):
                    tx_type = "income"
                elif INCOME_KEYWORDS_RE.search(desc) and not EXPENSE_KEYWORDS_RE.search(desc):
                    tx_type = "income"
                else:
                    tx_type = "expense"

            if amt_final > 0:
                parsed_rows.append({
                    "date": iso_date,
                    "amount": round(amt_final, 2),
                    "type": tx_type,
                    "item_name": clean_statement_merchant(desc, tx_type),
                })
                continue

        # Pattern 3: Generic / Halyk compact style — Description followed by 1 or 2 amounts at end
        m_tail = re.match(
            r"^(?P<desc>.+?)\s+"
            r"(?P<amt1>[+-]?\s*\d[\d\s\u00a0]*[.,]\d{2})\s*(?:₸|KZT|USD|EUR|RUB|тенге|руб|\$|€|₽)?"
            r"(?:\s+(?P<amt2>[+-]?\s*\d[\d\s\u00a0]*[.,]\d{2})\s*(?:₸|KZT|USD|EUR|RUB|тенге|руб|\$|€|₽)?)?$",
            rest_clean,
            re.IGNORECASE,
        )
        if m_tail:
            desc = m_tail.group("desc").strip()
            raw_a1 = m_tail.group("amt1").strip()
            raw_a2 = (m_tail.group("amt2") or "").strip()
            a1 = _parse_money(raw_a1)
            a2 = _parse_money(raw_a2) if raw_a2 else None

            # Ensure desc doesn't contain other stray decimal columns
            extra_decimals = re.findall(r"\b\d+[.,]\d{2}\b", desc)
            if not extra_decimals and a1 is not None:
                chosen_raw = raw_a1
                chosen_val: float | None = a1
                if a2 is not None:
                    if abs(a2) == 0:
                        chosen_raw, chosen_val = raw_a1, a1
                    elif abs(a1) == 0:
                        chosen_raw, chosen_val = raw_a2, a2
                    elif abs(a1) == abs(a2):
                        chosen_raw, chosen_val = raw_a2 if raw_a2.startswith(("+", "-")) else raw_a1, a2
                    else:
                        chosen_val = None

                if chosen_val is not None and abs(chosen_val) > 0:
                    if chosen_raw.startswith("-"):
                        tx_type = "expense"
                    elif chosen_raw.startswith("+"):
                        tx_type = "income"
                    elif INCOME_KEYWORDS_RE.search(desc) and not EXPENSE_KEYWORDS_RE.search(desc):
                        tx_type = "income"
                    else:
                        tx_type = "expense"

                    parsed_rows.append({
                        "date": iso_date,
                        "amount": round(abs(chosen_val), 2),
                        "type": tx_type,
                        "item_name": clean_statement_merchant(desc, tx_type),
                    })
                    continue

        # If the block had a valid date and a decimal number XX,XX / XX.XX, queue for compact AI fallback
        if re.search(r"\d[.,]\d{2}\b", rest_clean):
            unparsed_blocks.append(line)

    return parsed_rows, unparsed_blocks


def clean_gemini_json(raw_text: str) -> dict[str, Any]:
    """Strip markdown codeblocks and parse JSON safely, salvaging truncated transaction arrays."""
    text = raw_text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    # Salvage truncated JSON response by recovering all complete {"date": ...} objects
    tx_matches = re.findall(r"\{[^{}]*\"amount\"\s*:[^{}]*\}", text)
    salvaged_txs = []
    for m in tx_matches:
        try:
            salvaged_txs.append(json.loads(m))
        except Exception:
            continue
    if salvaged_txs:
        bank_m = re.search(r'"bank_name"\s*:\s*"([^"]+)"', text)
        curr_m = re.search(r'"currency"\s*:\s*"([^"]+)"', text)
        cb_m = re.search(r'"closing_balance"\s*:\s*(-?\d+(?:\.\d+)?)', text)
        return {
            "bank_name": bank_m.group(1) if bank_m else None,
            "currency": curr_m.group(1) if curr_m else "KZT",
            "closing_balance": float(cb_m.group(1)) if cb_m else None,
            "transactions": salvaged_txs,
        }
    logger.warning("Failed to decode JSON from Gemini (len=%d)", len(raw_text))
    return {}


def _redact_pii(text_content: str, known_names: list[str] | None = None) -> str:
    """Redact IBAN, card numbers, IIN/BIN, counterparty names, and known user names."""
    text_content = re.sub(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", "[IBAN_MASKED]", text_content)
    text_content = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[CARD_MASKED]", text_content)
    text_content = re.sub(r"\b\d{12}\b", "[ID_MASKED]", text_content)
    text_content = re.sub(
        r"(?:перевод\s+(?:от|кому|клиенту)?\s*)([А-ЯЁA-Z][а-яёa-z]+\s+[А-ЯЁA-Z]\.(?:\s*[А-ЯЁA-Z]\.?)?)",
        r"Перевод [ИМЯ_СКРЫТО]",
        text_content,
        flags=re.IGNORECASE,
    )
    try:
        from src.services.pii_guardrail_service import PIIGuardrailService
        text_content = PIIGuardrailService.mask_text(text_content, known_names=known_names)
    except Exception:
        pass
    return text_content


def extract_and_redact_pdf_chunks(
    pdf_bytes: bytes,
    max_pages: int = 150,
    chars_per_chunk: int = 14000,
    known_names: list[str] | None = None,
) -> tuple[list[str], bool]:
    """
    Extracts text from up to max_pages of a PDF, redacts PII, and splits into manageable chunks
    so full 1-year statements are parsed completely without hitting Gemini output token limits.
    """
    if not pypdf:
        return [], True

    try:
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        pages = reader.pages[:max_pages]
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_len = 0

        for idx, page in enumerate(pages, start=1):
            page_text = (page.extract_text() or "").strip()
            if not page_text:
                continue
            redacted_page = f"--- СТРАНИЦА {idx} ---\n" + _redact_pii(page_text, known_names=known_names)
            if current_len + len(redacted_page) > chars_per_chunk and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [redacted_page]
                current_len = len(redacted_page)
            else:
                current_chunk.append(redacted_page)
                current_len += len(redacted_page)

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        total_chars = sum(len(c) for c in chunks)
        if not chunks or total_chars < 40:
            return [], True

        return chunks, False
    except Exception as exc:
        logger.warning("Local PDF extraction failed: %s", exc)
        return [], True


def extract_and_redact_pdf_text(
    pdf_bytes: bytes,
    max_pages: int = 150,
    known_names: list[str] | None = None,
) -> tuple[str, bool]:
    """Backwards-compatible wrapper returning full joined text."""
    chunks, is_scanned = extract_and_redact_pdf_chunks(
        pdf_bytes, max_pages=max_pages, chars_per_chunk=500000, known_names=known_names
    )
    if is_scanned or not chunks:
        return "", True
    return "\n\n".join(chunks), False


STATEMENT_PROMPT = (
    "Ты специализированный финансовый анализатор банковских выписок (PDF) приложения Smart Bujet.\n"
    "Твоя задача — извлечь из предоставленного фрагмента банковской выписки все финансовые операции, "
    "начальный и конечный баланс, валюту счета, банк и период выписки.\n\n"
    "СТРОГИЕ ПРАВИЛА:\n"
    "1. Извлеки все строки операций из текста. Для каждой операции укажи:\n"
    "   - 'date': дата операции в формате 'YYYY-MM-DD' (или 'YYYY-MM-DDTHH:MM:SS').\n"
    "   - 'amount': сумма в виде положительного числа (float/int).\n"
    "   - 'type': 'expense' (списание, покупка, комиссия, исходящий перевод) или 'income' (пополнение, зарплата, входящий перевод, кешбэк, проценты).\n"
    "   - 'item_name': получатель/магазин/описание (например 'Magnum', 'Yandex Go', 'Зарплата', 'Перевод'). Не включай личные ФИО.\n"
    "   - 'category': категория строго из списка: 'Продукты', 'Еда вне дома', 'Ребёнок', 'Транспорт', 'Здоровье', 'Обязательные расходы', 'Питомец', 'Развлечения', 'Образование', 'Подписки', 'Ремонт', 'Шоппинг', 'Зарплата', 'Подарок', 'Денежный перевод', 'Прочее'.\n"
    "2. Исключи внутренние переводы между своими счетами/депозитами внутри одного банка (например, 'На Kaspi Депозит', 'С Kaspi Депозита').\n"
    "3. Извлеки метаданные выписки (если они видны в этом фрагменте, иначе null):\n"
    "   - 'bank_name': название банка (например 'Kaspi Bank', 'Halyk Bank', 'ForteBank', 'Сбербанк', 'Тинькофф').\n"
    "   - 'currency': валюта ('KZT', 'USD', 'RUB', 'EUR'). По умолчанию 'KZT'.\n"
    "   - 'period_start': дата начала выписки 'YYYY-MM-DD' или null.\n"
    "   - 'period_end': дата конца выписки 'YYYY-MM-DD' или null.\n"
    "   - 'starting_balance': начальный остаток (float или null).\n"
    "   - 'closing_balance': итоговый остаток на конец периода / исходящий остаток (float или null).\n\n"
    "Верни СТРОГО валидный JSON:\n"
    "{\n"
    '  "bank_name": "Kaspi Bank",\n'
    '  "currency": "KZT",\n'
    '  "period_start": "2025-01-01",\n'
    '  "period_end": "2025-12-31",\n'
    '  "starting_balance": 50000.0,\n'
    '  "closing_balance": 125000.0,\n'
    '  "transactions": [\n'
    '    {"date": "2025-01-05", "amount": 3200.0, "type": "expense", "item_name": "Magnum", "category": "Продукты"}\n'
    "  ]\n"
    "}"
)

MERCHANT_AND_META_PROMPT = (
    "Ты финансовый классификатор банковских выписок приложения Smart Bujet.\n"
    "Тебе переданы:\n"
    "1) Шапка/подвал банковской выписки (для извлечения банка, валюты, дат периода и исходящего остатка НА КОНЕЦ периода).\n"
    "2) Пронумерованный список уникальных мерчантов/описаний из выписки в формате 'ID: E|Название' (расход) или 'ID: I|Название' (доход).\n\n"
    "ПРАВИЛА:\n"
    "1. Для каждого ID из списка мерчантов выбери ровно одну категорию из списка:\n"
    "   'Продукты', 'Еда вне дома', 'Ребёнок', 'Транспорт', 'Здоровье', 'Обязательные расходы', "
    "'Питомец', 'Развлечения', 'Образование', 'Подписки', 'Ремонт', 'Шоппинг', 'Зарплата', 'Подарок', 'Денежный перевод', 'Прочее'.\n"
    "2. Из шапки/подвала извлеки:\n"
    "   - 'bank_name': название банка ('Halyk Bank', 'Kaspi Bank', 'ForteBank' и т.д. или null)\n"
    "   - 'currency': 'KZT', 'USD', 'RUB', 'EUR' (по умолчанию 'KZT')\n"
    "   - 'period_start': 'YYYY-MM-DD' или null\n"
    "   - 'period_end': 'YYYY-MM-DD' или null\n"
    "   - 'starting_balance': входящий остаток на начало периода (float или null)\n"
    "   - 'closing_balance': исходящий (конечный / доступный) остаток на счете НА КОНЕЦ периода (float или null). Не путай с входящим остатком!\n\n"
    "Верни СТРОГО компактный JSON:\n"
    "{\n"
    '  "bank_name": "Halyk Bank",\n'
    '  "currency": "KZT",\n'
    '  "period_start": "2025-01-14",\n'
    '  "period_end": "2026-10-22",\n'
    '  "starting_balance": 0.0,\n'
    '  "closing_balance": 3389.0,\n'
    '  "merchants": {"0": "Продукты", "1": "Еда вне дома"}\n'
    "}"
)


class BankStatementService:
    def __init__(self, session: AsyncSession, api_key: str | None = None, model_name: str | None = None):
        self.session = session
        self.api_key = api_key or settings.google_token
        self.client = genai.Client(api_key=self.api_key) if (self.api_key and genai is not None) else None
        self.model_name = model_name or settings.gemini_model

    async def _call_gemini_chunk(self, contents: list[Any]) -> dict[str, Any]:
        """Call Gemini for a single chunk/document with JSON mime type config."""
        cfg = (
            types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            if types is not None and hasattr(types, "GenerateContentConfig")
            else None
        )
        kwargs: dict[str, Any] = {"model": self.model_name, "contents": contents}
        if cfg is not None:
            kwargs["config"] = cfg

        response = await asyncio.to_thread(self.client.models.generate_content, **kwargs)
        raw_text = response.text or ""
        parsed = clean_gemini_json(raw_text)
        return parsed if isinstance(parsed, dict) else {}

    async def _load_user_alias_map(self, user_id: int | None) -> dict[str, str]:
        """Load user's existing item alias hashes -> category name in a single SQL query."""
        if not user_id or not self.session:
            return {}
        try:
            stmt = (
                select(UserItemAlias.item_name_normalized, Category.name)
                .join(Category, UserItemAlias.category_id == Category.id)
                .where(UserItemAlias.user_id == user_id)
            )
            res = await self.session.execute(stmt)
            rows = res.all() if hasattr(res, "all") else []
            if asyncio.iscoroutine(rows):
                rows = await rows
            if isinstance(rows, (list, tuple)):
                return {
                    str(r[0]): str(r[1])
                    for r in rows
                    if isinstance(r, (list, tuple)) and len(r) >= 2 and r[0] and r[1]
                }
        except Exception as exc:
            logger.debug("Could not load user aliases for statement import: %s", exc)
        return {}

    async def _parse_via_hybrid_local(
        self,
        full_text: str,
        local_rows: list[dict[str, Any]],
        unparsed_blocks: list[str],
        user_id: int | None = None,
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """
        Fast hybrid pipeline:
        1. Uses locally extracted rows (0 tokens for row extraction).
        2. If a few rows had unusual formatting (unparsed_blocks), parses only those blocks.
        3. Deduplicates all unique merchants across the entire statement, resolves known aliases
           and local rules (0 tokens), and sends at most 1 compact batch request to Gemini
           for unknown merchants + header/footer metadata verification.
        """
        meta = extract_statement_metadata_regex(full_text)

        # If any candidate rows failed local regex, parse just those rows via Gemini
        if unparsed_blocks and self.client:
            for i in range(0, len(unparsed_blocks), 60):
                batch_lines = "\n".join(unparsed_blocks[i : i + 60])
                fallback_res = await self._call_gemini_chunk(
                    [STATEMENT_PROMPT, f"СТРОКИ ВЫПИСКИ:\n{batch_lines}"]
                )
                for tx in fallback_res.get("transactions") or []:
                    if isinstance(tx, dict) and tx.get("amount"):
                        tx_type = "income" if tx.get("type") == "income" else "expense"
                        local_rows.append({
                            "date": tx.get("date"),
                            "amount": tx.get("amount"),
                            "type": tx_type,
                            "item_name": clean_statement_merchant(str(tx.get("item_name") or ""), tx_type),
                            "category": tx.get("category"),
                        })

        alias_map = await self._load_user_alias_map(user_id)

        # Deduplicate unique (type, item_name) pairs that still need a category
        resolved_categories: dict[tuple[str, str], str] = {}
        unknown_pairs: list[tuple[str, str]] = []

        for row in local_rows:
            if row.get("category"):
                continue
            key = (row["type"], row["item_name"])
            if key in resolved_categories:
                continue

            # Tier 1: UserItemAlias cache in DB (via HMAC blind_index)
            b_idx = blind_index(row["item_name"])
            if b_idx in alias_map:
                resolved_categories[key] = alias_map[b_idx]
                continue

            # Tier 2: Deterministic local merchant rules (0 tokens)
            local_cat = match_local_category(row["item_name"], row["type"])
            if local_cat:
                resolved_categories[key] = local_cat
                continue

            resolved_categories[key] = ""
            unknown_pairs.append(key)

        # Prepare compact header + footer snippet (~3000 chars) so Gemini can also verify closing_balance
        header_footer_snippet = full_text[:1800]
        if len(full_text) > 2200:
            header_footer_snippet += "\n...\n" + full_text[-1800:]

        need_meta_verify = (
            meta["closing_balance"] is None
            or meta["bank_name"] is None
            or meta["period_end"] is None
        )

        if self.client and (unknown_pairs or need_meta_verify):
            batch_size = 100
            batches = [
                unknown_pairs[i : i + batch_size]
                for i in range(0, max(1, len(unknown_pairs)), batch_size)
            ]
            total_steps = len(batches)
            for b_idx, batch in enumerate(batches, start=1):
                lines = [
                    f"{idx}: {'I' if t == 'income' else 'E'}|{name}"
                    for idx, (t, name) in enumerate(batch)
                ]
                merchants_block = "\n".join(lines) if lines else "(нет неизвестных мерчантов)"
                prompt_input = (
                    f"ШАПКА И ПОДВАЛ ВЫПИСКИ:\n{header_footer_snippet}\n\n"
                    f"СПИСОК УНИКАЛЬНЫХ МЕРЧАНТОВ ({len(batch)} шт.):\n{merchants_block}"
                )
                ai_data = await self._call_gemini_chunk([MERCHANT_AND_META_PROMPT, prompt_input])
                if isinstance(ai_data, dict):
                    if not meta["bank_name"] and ai_data.get("bank_name"):
                        meta["bank_name"] = ai_data["bank_name"]
                    if not meta["currency"] and ai_data.get("currency"):
                        meta["currency"] = ai_data["currency"]
                    if not meta["period_start"] and ai_data.get("period_start"):
                        meta["period_start"] = ai_data["period_start"]
                    if not meta["period_end"] and ai_data.get("period_end"):
                        meta["period_end"] = ai_data["period_end"]
                    if meta["starting_balance"] is None and ai_data.get("starting_balance") is not None:
                        meta["starting_balance"] = ai_data["starting_balance"]
                    if meta["closing_balance"] is None and ai_data.get("closing_balance") is not None:
                        meta["closing_balance"] = ai_data["closing_balance"]

                    ai_merchants = ai_data.get("merchants")
                    if isinstance(ai_merchants, dict):
                        for idx, pair_key in enumerate(batch):
                            cat_val = ai_merchants.get(str(idx)) or ai_merchants.get(idx)
                            if isinstance(cat_val, str) and cat_val.strip():
                                resolved_categories[pair_key] = cat_val.strip()

                if progress_callback:
                    try:
                        await progress_callback(b_idx, total_steps)
                    except Exception:
                        pass

        for row in local_rows:
            if not row.get("category"):
                key = (row["type"], row["item_name"])
                cat = resolved_categories.get(key)
                row["category"] = cat if cat else ("Зарплата" if row["type"] == "income" else "Прочее")

        return {
            "bank_name": meta["bank_name"],
            "currency": meta["currency"] or "KZT",
            "period_start": meta["period_start"],
            "period_end": meta["period_end"],
            "starting_balance": meta["starting_balance"],
            "closing_balance": meta["closing_balance"],
            "transactions": local_rows,
        }

    async def parse_single_pdf(
        self,
        pdf_bytes: bytes,
        filename: str,
        user_id: int | None = None,
        known_names: list[str] | None = None,
        progress_callback: Callable[[int, int], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """Parse one bank statement PDF (using Hybrid Local Regex + Deduplicated AI Categorization)."""
        if user_id is not None:
            from src.services.ai_service import ai_rate_limiter
            allowed, reason = ai_rate_limiter.check_and_record(user_id)
            if not allowed:
                return {"error": reason or "Превышен лимит запросов к AI. Подождите немного.", "transactions": []}

        if not self.client:
            logger.error("Gemini client not initialized for BankStatementService")
            return {"error": "AI service unavailable", "transactions": []}

        if len(pdf_bytes) > 15 * 1024 * 1024:
            return {"error": "Размер файла превышает лимит 15 МБ", "transactions": []}

        chunks, is_scanned = extract_and_redact_pdf_chunks(
            pdf_bytes, max_pages=150, chars_per_chunk=14000, known_names=known_names
        )

        try:
            if is_scanned or not chunks:
                pdf_part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
                parsed = await self._call_gemini_chunk([STATEMENT_PROMPT, pdf_part])
                return parsed or {"error": "Invalid response format", "transactions": []}

            full_text = "\n\n".join(chunks)
            local_rows, unparsed_blocks = extract_rows_locally(full_text)

            # Fast path: if local regex extracted rows (and captured the majority of candidate lines),
            # avoid chunked LLM calls and classify only unique unknown merchants (95-98% token savings!)
            if local_rows and len(local_rows) >= len(unparsed_blocks):
                logger.info(
                    "Hybrid statement parser extracted %d rows locally (%d fallback lines) from '%s'",
                    len(local_rows),
                    len(unparsed_blocks),
                    filename,
                )
                return await self._parse_via_hybrid_local(
                    full_text=full_text,
                    local_rows=local_rows,
                    unparsed_blocks=unparsed_blocks,
                    user_id=user_id,
                    progress_callback=progress_callback,
                )

            # Fallback path: chunked LLM extraction for non-standard bank layouts or mocked unit tests
            regex_meta = extract_statement_metadata_regex(full_text)
            total_chunks = len(chunks)
            merged: dict[str, Any] = {
                "bank_name": regex_meta["bank_name"],
                "currency": regex_meta["currency"],
                "period_start": regex_meta["period_start"],
                "period_end": regex_meta["period_end"],
                "starting_balance": regex_meta["starting_balance"],
                "closing_balance": regex_meta["closing_balance"],
                "transactions": [],
            }

            sem = asyncio.Semaphore(2)
            completed_chunks = 0

            async def process_chunk(idx: int, chunk_text: str) -> tuple[int, dict[str, Any]]:
                nonlocal completed_chunks
                async with sem:
                    res = await self._call_gemini_chunk(
                        [
                            STATEMENT_PROMPT,
                            f"ФРАГМЕНТ ВЫПИСКИ ({idx + 1} из {total_chunks}, PII ОБЕЗЛИЧЕНО):\n{chunk_text}",
                        ]
                    )
                    completed_chunks += 1
                    if progress_callback:
                        try:
                            await progress_callback(completed_chunks, total_chunks)
                        except Exception:
                            pass
                    return idx, res

            tasks = [process_chunk(i, c) for i, c in enumerate(chunks)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for item in sorted(
                (r for r in results if isinstance(r, tuple)), key=lambda x: x[0]
            ):
                _, chunk_data = item
                if not isinstance(chunk_data, dict):
                    continue
                if not merged["bank_name"] and chunk_data.get("bank_name"):
                    merged["bank_name"] = chunk_data["bank_name"]
                if not merged["currency"] and chunk_data.get("currency"):
                    merged["currency"] = chunk_data["currency"]
                if not merged["period_start"] and chunk_data.get("period_start"):
                    merged["period_start"] = chunk_data["period_start"]
                if chunk_data.get("period_end"):
                    if not merged["period_end"] or str(chunk_data["period_end"]) > str(merged["period_end"]):
                        merged["period_end"] = chunk_data["period_end"]
                if merged["starting_balance"] is None and chunk_data.get("starting_balance") is not None:
                    merged["starting_balance"] = chunk_data["starting_balance"]
                if chunk_data.get("closing_balance") is not None:
                    if merged["closing_balance"] is None or (
                        merged["closing_balance"] == 0 and chunk_data["closing_balance"] != 0
                    ):
                        merged["closing_balance"] = chunk_data["closing_balance"]

                txs = chunk_data.get("transactions")
                if isinstance(txs, list):
                    merged["transactions"].extend(txs)

            return merged
        except Exception as exc:
            logger.error("Failed to parse PDF statement '%s': %s", filename, exc)
            return {"error": str(exc), "transactions": []}

    async def import_statements(
        self,
        user_id: int,
        files: list[tuple[str, bytes]],
        progress_callback: Callable[[str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """
        Process one or multiple PDF bank statements for the user,
        persist transactions, calibrate initial balance to match closing balance,
        cache merchant aliases, and return summary stats.
        """
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")

        files = files[:3]

        cat_service = CategoryService(self.session)
        if hasattr(cat_service, "get_categories") and callable(getattr(cat_service, "get_categories")):
            res = cat_service.get_categories(user_id=user.id)
            categories = await res if asyncio.iscoroutine(res) or hasattr(res, "__await__") else res
        elif hasattr(cat_service, "get_all_categories") and callable(getattr(cat_service, "get_all_categories")):
            res = cat_service.get_all_categories()
            categories = await res if asyncio.iscoroutine(res) or hasattr(res, "__await__") else res
        else:
            categories = []
        if categories is None:
            categories = []
        cat_map: dict[tuple[str, str], Category] = {
            (c.name.lower(), c.type.value if hasattr(c.type, "value") else str(c.type)): c
            for c in categories
        }
        cat_by_name: dict[str, Category] = {c.name.lower(): c for c in categories}
        default_expense_cat = cat_by_name.get("прочее") or (categories[0] if categories else None)
        default_income_cat = cat_by_name.get("зарплата") or cat_by_name.get("доход") or default_expense_cat

        existing_keys: set[tuple] = set()
        try:
            db_res = await self.session.execute(
                select(Transaction.transaction_date, Transaction.amount, Transaction.type, Transaction.item_name)
                .where(Transaction.user_id == user.id, Transaction.source == TransactionSource.statement)
            )
            raw_all = db_res.all() if hasattr(db_res, "all") else []
            if asyncio.iscoroutine(raw_all):
                raw_all = await raw_all
            if isinstance(raw_all, (list, tuple, set)):
                existing_keys = {
                    (tx[0].date() if tx[0] else None, tx[1], tx[2], (tx[3] or "")[:30].strip().lower())
                    for tx in raw_all
                    if isinstance(tx, (tuple, list)) and len(tx) >= 4
                }
        except Exception as e:
            logger.warning("Could not pre-fetch existing statement transactions: %s", e)

        existing_alias_hashes: set[str] = set()
        has_real_alias_preload = False
        try:
            alias_res = await self.session.execute(
                select(UserItemAlias.item_name_normalized).where(UserItemAlias.user_id == user.id)
            )
            raw_aliases = alias_res.all() if hasattr(alias_res, "all") else []
            if asyncio.iscoroutine(raw_aliases):
                raw_aliases = await raw_aliases
            if isinstance(raw_aliases, (list, tuple)):
                has_real_alias_preload = True
                existing_alias_hashes = {
                    str(a[0]) for a in raw_aliases if isinstance(a, (tuple, list)) and len(a) >= 1 and a[0]
                }
        except Exception:
            pass

        all_tx_records: list[dict[str, Any]] = []
        bank_names: set[str] = set()
        detected_currencies: list[str] = []
        latest_closing_balance: float | None = None
        latest_statement_date: datetime | None = None
        earliest_statement_date: datetime | None = None

        seen_batch: set[tuple] = set()
        known = [user.first_name] if user.first_name else None
        total_files = len(files)

        for file_idx, (filename, pdf_bytes) in enumerate(files, start=1):
            async def on_chunk_progress(done_chunks: int, total_chunks: int, f_idx: int = file_idx) -> None:
                if progress_callback and total_chunks > 1:
                    await progress_callback(
                        f"⏳ <b>Обрабатываю выписку {f_idx} из {total_files}...</b>\n"
                        f"Проанализировано этапов: <b>{done_chunks} из {total_chunks}</b>"
                    )

            parse_kwargs: dict[str, Any] = {
                "user_id": user.id,
                "known_names": known,
            }
            if progress_callback is not None:
                parse_kwargs["progress_callback"] = on_chunk_progress

            statement_data = await self.parse_single_pdf(pdf_bytes, filename, **parse_kwargs)
            gc.collect()

            bank = statement_data.get("bank_name")
            if bank:
                bank_names.add(bank)

            currency = statement_data.get("currency")
            if currency:
                detected_currencies.append(currency.upper())

            p_end_str = statement_data.get("period_end")
            p_start_str = statement_data.get("period_start")

            p_end = None
            if p_end_str:
                try:
                    p_end = datetime.fromisoformat(p_end_str).replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            p_start = None
            if p_start_str:
                try:
                    p_start = datetime.fromisoformat(p_start_str).replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            if p_start and (earliest_statement_date is None or p_start < earliest_statement_date):
                earliest_statement_date = p_start

            cb = statement_data.get("closing_balance")
            if p_end and (latest_statement_date is None or p_end >= latest_statement_date):
                latest_statement_date = p_end
                if cb is not None:
                    try:
                        latest_closing_balance = float(cb)
                    except Exception:
                        pass
            elif latest_closing_balance is None and cb is not None:
                try:
                    latest_closing_balance = float(cb)
                except Exception:
                    pass

            for tx in statement_data.get("transactions", []):
                if not isinstance(tx, dict):
                    continue
                amt = tx.get("amount")
                if amt is None:
                    continue
                try:
                    num_amt = abs(float(amt))
                    if num_amt <= 0:
                        continue
                except Exception:
                    continue

                tx_date_raw = tx.get("date")
                tx_date = datetime.now(timezone.utc)
                if tx_date_raw:
                    try:
                        parsed_dt = datetime.fromisoformat(str(tx_date_raw))
                        if parsed_dt.tzinfo is None:
                            parsed_dt = parsed_dt.replace(tzinfo=timezone.utc)
                        tx_date = parsed_dt
                    except Exception:
                        pass

                tx_type = CategoryType.income if tx.get("type") == "income" else CategoryType.expense
                item_name = str(tx.get("item_name") or "Операция по выписке").strip()[:200]
                amount_dec = Decimal(str(round(num_amt, 2)))

                dedup_key = (tx_date.date(), amount_dec, tx_type, item_name[:30].lower())
                if dedup_key in seen_batch or dedup_key in existing_keys:
                    continue
                seen_batch.add(dedup_key)

                all_tx_records.append({
                    "date": tx_date,
                    "amount": amount_dec,
                    "type": tx_type,
                    "item_name": item_name,
                    "category": str(tx.get("category") or "").strip(),
                })

        if not all_tx_records:
            return {
                "success": False,
                "error": "Не удалось обнаружить новые операции в загруженных выписках.",
                "total_count": 0,
            }

        all_tx_records.sort(key=lambda x: x["date"])

        if earliest_statement_date is None:
            earliest_statement_date = all_tx_records[0]["date"]
        if latest_statement_date is None:
            latest_statement_date = all_tx_records[-1]["date"]

        total_period_expense = Decimal("0")
        total_period_income = Decimal("0")

        for item in all_tx_records:
            raw_cat = item["category"].lower()
            cat_name = CATEGORY_ALIASES.get(raw_cat, raw_cat)
            type_str = item["type"].value if hasattr(item["type"], "value") else str(item["type"])
            matched_cat = cat_map.get((cat_name, type_str)) or cat_by_name.get(cat_name)
            if not matched_cat:
                matched_cat = default_income_cat if item["type"] == CategoryType.income else default_expense_cat

            naive_dt = item["date"].replace(tzinfo=None) if item["date"].tzinfo else item["date"]

            tx_obj = Transaction(
                user_id=user.id,
                family_group_id=user.family_group_id,
                category_id=matched_cat.id if matched_cat else 1,
                amount=item["amount"],
                type=item["type"],
                item_name=item["item_name"],
                transaction_date=naive_dt,
                created_at=naive_dt,
                source=TransactionSource.statement,
                raw_text=None,
            )
            self.session.add(tx_obj)

            # Cache merchant -> category in UserItemAlias so future statements/messages cost 0 tokens
            if (
                has_real_alias_preload
                and matched_cat
                and matched_cat.name not in ("Прочее", "Денежный перевод")
                and item["item_name"]
            ):
                b_hash = blind_index(item["item_name"])
                if b_hash not in existing_alias_hashes:
                    existing_alias_hashes.add(b_hash)
                    self.session.add(
                        UserItemAlias(
                            user_id=user.id,
                            item_name_normalized=b_hash,
                            category_id=matched_cat.id,
                            usage_count=1,
                        )
                    )

            if item["type"] == CategoryType.income:
                total_period_income += item["amount"]
            else:
                total_period_expense += item["amount"]

        if detected_currencies:
            user.currency = detected_currencies[0]

        net_cashflow = total_period_income - total_period_expense
        if latest_closing_balance is not None:
            # Allow negative calculated_initial when outgoing transfers to deposits/savings were excluded
            calculated_initial = Decimal(str(latest_closing_balance)) - net_cashflow
            user.initial_balance = calculated_initial
        elif user.initial_balance is None:
            user.initial_balance = Decimal("0.0")

        await self.session.commit()

        now = datetime.now(timezone.utc)
        start_current_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)

        current_month_expense = sum(
            x["amount"] for x in all_tx_records
            if x["type"] == CategoryType.expense and x["date"] >= start_current_month
        )
        current_month_income = sum(
            x["amount"] for x in all_tx_records
            if x["type"] == CategoryType.income and x["date"] >= start_current_month
        )

        tx_service = TransactionService(self.session)
        live_balance_data = await tx_service.get_user_balance(user.id)

        # Ensure live current_balance matches statement closing_balance even if prior transactions existed
        if latest_closing_balance is not None and isinstance(live_balance_data.get("current_balance"), (int, float, Decimal)):
            target_cb = Decimal(str(round(latest_closing_balance, 2)))
            actual_cb = Decimal(str(round(float(live_balance_data["current_balance"]), 2)))
            diff = target_cb - actual_cb
            if abs(diff) >= Decimal("0.01"):
                user.initial_balance = Decimal(str(user.initial_balance or 0)) + diff
                await self.session.commit()
                live_balance_data["current_balance"] = float(target_cb)

        period_label = (
            f"{earliest_statement_date.strftime('%d.%m.%Y')} — {latest_statement_date.strftime('%d.%m.%Y')}"
        )

        return {
            "success": True,
            "bank_names": list(bank_names) or ["Банк"],
            "period_label": period_label,
            "total_count": len(all_tx_records),
            "total_expense": float(total_period_expense),
            "total_income": float(total_period_income),
            "current_month_expense": float(current_month_expense),
            "current_month_income": float(current_month_income),
            "current_balance": live_balance_data["current_balance"],
            "currency": user.currency or "KZT",
        }
