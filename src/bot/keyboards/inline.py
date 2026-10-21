from __future__ import annotations

from typing import Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

def currency_keyboard() -> InlineKeyboardMarkup:
    currencies = ["KZT", "RUB", "USD", "EUR"]
    buttons = [
        InlineKeyboardButton(text=c, callback_data=f"currency_{c}") for c in currencies
    ]
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def get_miniapp_url() -> str:
    from src.core.config import settings
    domain = settings.domain
    if not domain or domain == "localhost":
        domain = "85.198.89.188.sslip.io:8443"
    elif ":" not in domain and "sslip.io" in domain:
        domain = f"{domain}:8443"
    return f"https://{domain}/app"

def welcome_back_keyboard(miniapp_url: str | None = None) -> InlineKeyboardMarkup:
    if miniapp_url is None:
        miniapp_url = get_miniapp_url()
    rows = []
    if miniapp_url:
        rows.append([InlineKeyboardButton(text="📱 Открыть журнал транзакций", web_app=WebAppInfo(url=miniapp_url))])
        deposits_url = f"{miniapp_url}?page=deposits" if "?" not in miniapp_url else f"{miniapp_url}&page=deposits"
        credits_url = f"{miniapp_url}?page=credits" if "?" not in miniapp_url else f"{miniapp_url}&page=credits"
        analytics_url = f"{miniapp_url}?page=analytics" if "?" not in miniapp_url else f"{miniapp_url}&page=analytics"
        rows.append([
            InlineKeyboardButton(text="🏦 Депозиты", web_app=WebAppInfo(url=deposits_url)),
            InlineKeyboardButton(text="💳 Кредиты", web_app=WebAppInfo(url=credits_url)),
            InlineKeyboardButton(text="📊 Аналитика", web_app=WebAppInfo(url=analytics_url)),
        ])
    rows.append([
        InlineKeyboardButton(text="📊 Сводка от агента", callback_data="sum:menu"),
        InlineKeyboardButton(text="💱 Изменить валюту", callback_data="change_currency"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def analytics_keyboard(analytics_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Открыть Аналитику", web_app=WebAppInfo(url=analytics_url))]
        ]
    )

def miniapp_keyboard(miniapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Открыть журнал транзакций", web_app=WebAppInfo(url=miniapp_url))]
        ]
    )

def deposits_keyboard(deposits_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏦 Открыть Депозиты и Валюту", web_app=WebAppInfo(url=deposits_url))]
        ]
    )

def credits_keyboard(credits_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Открыть Кредиты", web_app=WebAppInfo(url=credits_url))]
        ]
    )

def family_keyboard(family_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="👨‍👩‍👧‍👦 Открыть Семейный бюджет", web_app=WebAppInfo(url=family_url))]
        ]
    )

def confirm_transaction_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"tx_confirm_{tx_id}"),
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"tx_cancel_{tx_id}")
            ]
        ]
    )

def tx_toggle_keyboard(transactions: Any) -> InlineKeyboardMarkup:
    """Generate dynamic confirmation keyboard:
    - Row 1..N: Dynamic toggle button(s) [🔄 Это доход] / [🔄 Это расход] (for expense/income).
    - Bottom row: Always [📋 Вернуться в меню] (callback_data="sum:back:main").
    Works for single tx, batch txs, and transfers/deposits.
    """
    from src.models.category import CategoryType

    tx_list = [transactions] if not isinstance(transactions, list) else transactions
    rows = []

    if tx_list:
        if len(tx_list) == 1:
            tx = tx_list[0]
            tx_type = getattr(tx, "type", None)
            if tx_type == CategoryType.expense:
                rows.append([InlineKeyboardButton(text="🔄 Это доход", callback_data=f"tx_toggle:{tx.id}")])
            elif tx_type == CategoryType.income:
                rows.append([InlineKeyboardButton(text="🔄 Это расход", callback_data=f"tx_toggle:{tx.id}")])
        else:
            for idx, tx in enumerate(tx_list[:4], start=1):
                tx_type = getattr(tx, "type", None)
                if tx_type == CategoryType.expense:
                    rows.append([InlineKeyboardButton(text=f"🔄 #{idx} Это доход", callback_data=f"tx_toggle:{tx.id}")])
                elif tx_type == CategoryType.income:
                    rows.append([InlineKeyboardButton(text=f"🔄 #{idx} Это расход", callback_data=f"tx_toggle:{tx.id}")])

    # Always append the 'Вернуться в меню' button as the bottom row
    rows.append([InlineKeyboardButton(text="📋 Вернуться в меню", callback_data="sum:back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

