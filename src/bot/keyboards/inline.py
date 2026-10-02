from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def currency_keyboard() -> InlineKeyboardMarkup:
    currencies = ["KZT", "RUB", "USD", "EUR"]
    buttons = [
        InlineKeyboardButton(text=c, callback_data=f"currency_{c}") for c in currencies
    ]
    keyboard = [buttons[i:i+2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def confirm_transaction_keyboard(tx_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"tx_confirm_{tx_id}"),
                InlineKeyboardButton(text="❌ Отменить", callback_data=f"tx_cancel_{tx_id}")
            ]
        ]
    )
