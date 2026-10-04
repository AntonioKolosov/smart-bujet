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

def welcome_back_keyboard(miniapp_url: str | None = None) -> InlineKeyboardMarkup:
    rows = []
    if miniapp_url:
        rows.append([InlineKeyboardButton(text="📱 Открыть журнал транзакций", web_app=WebAppInfo(url=miniapp_url))])
        deposits_url = f"{miniapp_url}?page=deposits" if "?" not in miniapp_url else f"{miniapp_url}&page=deposits"
        family_url = f"{miniapp_url}?page=family" if "?" not in miniapp_url else f"{miniapp_url}&page=family"
        rows.append([
            InlineKeyboardButton(text="🏦 Депозиты", web_app=WebAppInfo(url=deposits_url)),
            InlineKeyboardButton(text="👨‍👩‍👧‍👦 Семья", web_app=WebAppInfo(url=family_url))
        ])
    rows.append([InlineKeyboardButton(text="💱 Изменить валюту", callback_data="change_currency")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

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

def tx_toggle_keyboard(transactions: Any) -> InlineKeyboardMarkup | None:
    """Generate dynamic toggle button: [🔄 Это доход] if expense, [🔄 Это расход] if income."""
    from src.models.category import CategoryType

    tx_list = [transactions] if not isinstance(transactions, list) else transactions
    if not tx_list:
        return None

    if len(tx_list) == 1:
        tx = tx_list[0]
        tx_type = getattr(tx, "type", None)
        if tx_type == CategoryType.expense:
            btn_text = "🔄 Это доход"
        elif tx_type == CategoryType.income:
            btn_text = "🔄 Это расход"
        else:
            return None
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=btn_text, callback_data=f"tx_toggle:{tx.id}")]
            ]
        )

    # Multi-item batch
    rows = []
    for idx, tx in enumerate(tx_list[:4], start=1):
        tx_type = getattr(tx, "type", None)
        if tx_type == CategoryType.expense:
            lbl = f"🔄 #{idx} Это доход"
        elif tx_type == CategoryType.income:
            lbl = f"🔄 #{idx} Это расход"
        else:
            continue
        rows.append([InlineKeyboardButton(text=lbl, callback_data=f"tx_toggle:{tx.id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None

