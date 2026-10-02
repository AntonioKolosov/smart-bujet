import json
from decimal import Decimal
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from src.core.config import settings


class AIService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.google_token
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = "gemini-2.5-flash"

    async def classify_text(
        self,
        text: str,
        categories: List[str]
    ) -> Dict[str, Any]:
        """
        Classify text transaction into category, amount, item_name, type.
        Returns: {"category": str, "amount": float, "item_name": str, "type": "expense"|"income"}
        """
        if not self.client:
            return {
                "category": categories[0] if categories else "Обязательные расходы",
                "type": "expense",
                "amount": None,
                "item_name": text
            }

        prompt = (
            f"Ты финансовый ассистент приложения учёта бюджета Smart Bujet.\n"
            f"Определи параметры транзакции из пользовательского сообщения: \"{text}\".\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"Верни ответ строго в JSON формате со следующими полями:\n"
            f'{{"category": "название из списка доступных", "type": "expense" или "income", "amount": число или null, "item_name": "краткое название позиции"}}\n'
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return json.loads(response.text)
        except Exception:
            return {
                "category": categories[0] if categories else "Обязательные расходы",
                "type": "expense",
                "amount": None,
                "item_name": text
            }

    async def parse_voice(
        self,
        audio_bytes: bytes,
        mime_type: str,
        categories: List[str]
    ) -> Dict[str, Any]:
        """
        In-memory voice message processing via types.Part.from_bytes.
        Never saves .ogg files to disk.
        """
        if not self.client:
            return {"category": "Обязательные расходы", "type": "expense", "amount": None, "item_name": "Голосовая запись"}

        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        prompt = (
            f"Прослушай аудиосообщение о расходе или доходе.\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"Верни JSON со следующими полями:\n"
            f'{{"category": "название из категорий", "type": "expense" или "income", "amount": число, "item_name": "название покупки", "raw_text": "распознанный текст"}}\n'
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[audio_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return json.loads(response.text)
        except Exception:
            return {"category": "Обязательные расходы", "type": "expense", "amount": None, "item_name": "Голосовая запись"}

    async def parse_receipt_photo(
        self,
        image_bytes: bytes,
        mime_type: str,
        categories: List[str]
    ) -> Dict[str, Any]:
        """
        In-memory receipt photo processing via types.Part.from_bytes.
        Never saves image files to disk.
        """
        if not self.client:
            return {"category": "Продукты", "type": "expense", "amount": None, "item_name": "Чек"}

        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        prompt = (
            f"Проанализируй фотографию чека/квитанции.\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"Извлеки общую итоговую сумму чека, название магазина или основную покупку, и выбери наиболее подходящую категорию.\n"
            f"Верни JSON со следующими полями:\n"
            f'{{"category": "название из категорий", "type": "expense", "amount": итоговая_сумма_числом, "item_name": "магазин/описание"}}\n'
        )

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[image_part, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            return json.loads(response.text)
        except Exception:
            return {"category": "Продукты", "type": "expense", "amount": None, "item_name": "Чек"}

