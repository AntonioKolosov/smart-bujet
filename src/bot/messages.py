from typing import List, Union
from src.models.transaction import Transaction
from src.models.category import CategoryType

CURRENCY_SYMBOLS: dict[str, str] = {
    "KZT": "₸",
    "RUB": "₽",
    "USD": "$",
    "EUR": "€",
}


def get_currency_symbol(currency_code: str | None) -> str:
    if not currency_code:
        return "₽"
    return CURRENCY_SYMBOLS.get(currency_code.upper(), currency_code)


def format_amount(amount: float, currency_code: str | None) -> str:
    symbol = get_currency_symbol(currency_code)
    formatted = f"{amount:,.2f}".replace(",", " ")
    return f"{formatted} {symbol}"


class BotMessages:
    @staticmethod
    def tx_success(transactions: Union[List[Transaction], Transaction], currency: str = "RUB") -> str:
        if not transactions:
            return "✅ <b>Записано!</b>"

        tx_list: List[Transaction] = [transactions] if isinstance(transactions, Transaction) else transactions
        if not tx_list:
            return "✅ <b>Записано!</b>"

        # Case 1: Single item formatting
        if len(tx_list) == 1:
            tx = tx_list[0]
            icon = "💸" if tx.type == CategoryType.expense else "💰"
            type_label = "Расход" if tx.type == CategoryType.expense else "Доход"
            cat_name = tx.category.name if tx.category else "Общее"

            amount_str = f"<b>{format_amount(tx.amount, currency)}</b>"
            discount_line = ""
            if tx.discount_amount and tx.discount_amount > 0 and tx.original_amount:
                amount_str += f" <s>{format_amount(tx.original_amount, currency)}</s>"
                discount_line = f"\n🏷️ <b>Скидка</b>: -{format_amount(tx.discount_amount, currency)}"

            return (
                f"✅ <b>Записано!</b>\n\n"
                f"{icon} <b>{type_label}</b>: {amount_str}{discount_line}\n"
                f"📌 Позиция: <b>{tx.item_name}</b>\n"
                f"📁 Категория: <b>{cat_name}</b>"
            )

        # Case 2: Multi-item batch formatting
        lines = [f"✅ <b>Записано ({len(tx_list)} поз.)!</b>\n"]
        total_expense = 0.0
        total_income = 0.0
        total_discount = 0.0

        for i, tx in enumerate(tx_list, start=1):
            icon = "💸" if tx.type == CategoryType.expense else "💰"
            cat_name = tx.category.name if tx.category else "Общее"
            if tx.discount_amount and tx.discount_amount > 0 and tx.original_amount:
                lines.append(
                    f"{i}. {icon} <b>{tx.item_name}</b> — {format_amount(tx.amount, currency)} "
                    f"<s>{format_amount(tx.original_amount, currency)}</s> (<i>{cat_name}</i>)"
                )
                total_discount += float(tx.discount_amount)
            else:
                lines.append(f"{i}. {icon} <b>{tx.item_name}</b> — {format_amount(tx.amount, currency)} (<i>{cat_name}</i>)")

            if tx.type == CategoryType.expense:
                total_expense += float(tx.amount)
            else:
                total_income += float(tx.amount)

        lines.append("")
        if total_discount > 0:
            lines.append(f"🏷️ Общая скидка: <b>-{format_amount(total_discount, currency)}</b>")

        if total_expense > 0 and total_income > 0:
            lines.append(f"💸 Итого расходов: <b>{format_amount(total_expense, currency)}</b>")
            lines.append(f"💰 Итого доходов: <b>{format_amount(total_income, currency)}</b>")
        elif total_expense > 0:
            lines.append(f"💰 <b>К оплате: {format_amount(total_expense, currency)}</b>")
        else:
            lines.append(f"💰 <b>Итого: {format_amount(total_income, currency)}</b>")

        return "\n".join(lines)

    @staticmethod
    def voice_clarification(recognized_text: str | None = None) -> str:
        if recognized_text:
            return (
                f"🎙️ Я распознал: «<i>{recognized_text}</i>», но не понял точную сумму.\n\n"
                f"<b>Повтори, пожалуйста!</b> Назови сумму и покупку, например:\n"
                f"• <i>«Кофе 250 рублей»</i>\n"
                f"• <i>«Такси 450»</i>\n"
                f"• <i>«Обед 600»</i>"
            )
        return (
            "🎙️ Не удалось разобрать аудиозапись или определить сумму.\n\n"
            "<b>Повтори, пожалуйста!</b> Скажи чётче, например:\n"
            "• <i>«Продукты 1500»</i>\n"
            "• <i>«Заправка 2000 рублей»</i>"
        )

    @staticmethod
    def text_clarification() -> str:
        return (
            "❓ Не удалось определить сумму.\n\n"
            "<b>Повтори, пожалуйста!</b> Укажи сумму и категорию, например:\n"
            "• <i>«Кофе 300»</i>\n"
            "• <i>«450 обед»</i>\n"
            "• <i>«Продукты 1200 руб»</i>"
        )

    @staticmethod
    def photo_clarification() -> str:
        return (
            "🧾 Не удалось распознать сумму в чеке.\n\n"
            "<b>Повтори, пожалуйста!</b> Сделай фото чека при хорошем освещении или введи трату текстом, например:\n"
            "• <i>«Пятёрочка 1240»</i>"
        )

    @staticmethod
    def service_unavailable() -> str:
        return "⚠️ Временная ошибка распознавания. Пожалуйста, попробуй ещё раз или отправь текстом."

    @staticmethod
    def welcome_new() -> str:
        return (
            "👋 <b>Добро пожаловать в Smart Bujet!</b>\n\n"
            "Я помогу вам легко вести учёт расходов и доходов.\n"
            "Пожалуйста, выберите вашу основную валюту:"
        )

    @staticmethod
    def welcome_back(first_name: str | None, currency: str) -> str:
        name_greeting = f", {first_name}" if first_name else ""
        symbol = get_currency_symbol(currency)
        return (
            f"👋 <b>С возвращением{name_greeting}!</b>\n\n"
            f"💰 Ваша текущая валюта: <b>{currency} ({symbol})</b>\n\n"
            f"💡 <b>Как записать трату:</b>\n"
            f"• Отправьте текст: <i>«Кофе 250»</i> или <i>«Рыба 4032 и хлеб 300»</i>\n"
            f"• Запишите голосовое сообщение\n"
            f"• Отправьте фото чека"
        )

    @staticmethod
    def currency_updated(currency: str) -> str:
        symbol = get_currency_symbol(currency)
        return f"✅ Валюта успешно установлена: <b>{currency} ({symbol})</b>"
