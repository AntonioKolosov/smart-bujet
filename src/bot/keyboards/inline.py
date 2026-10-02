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
        rows.append([InlineKeyboardButton(text="📱 Открыть MiniApp (Транзакции)", web_app=WebAppInfo(url=miniapp_url))])
    rows.append([InlineKeyboardButton(text="💱 Изменить валюту", callback_data="change_currency")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def miniapp_keyboard(miniapp_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📱 Открыть журнал транзакций", web_app=WebAppInfo(url=miniapp_url))]
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
