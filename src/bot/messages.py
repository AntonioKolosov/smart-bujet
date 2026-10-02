"""
Centralized Bot Message Templates.
Adheres to single-source-of-truth for UX scripts and localization.
"""

class BotMessages:
    @staticmethod
    def tx_success(item_name: str, amount: float, category_name: str, tx_type: str = "expense") -> str:
        icon = "💸" if tx_type == "expense" else "💰"
        type_label = "Расход" if tx_type == "expense" else "Доход"
        return (
            f"✅ <b>Записано!</b>\n\n"
            f"{icon} <b>{type_label}</b>: <b>{amount:,.2f} ₽</b>\n"
            f"📌 Позиция: <b>{item_name}</b>\n"
            f"📁 Категория: <b>{category_name}</b>"
        )

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
