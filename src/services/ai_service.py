import json
import logging
import re
from decimal import Decimal
from typing import Optional, Dict, Any, List
from google import genai
from google.genai import types
from src.core.config import settings

logger = logging.getLogger(__name__)


def normalize_ai_json(raw_text: str) -> List[Dict[str, Any]]:
    """
    Defensively parse JSON from Gemini and normalize to List[Dict].
    Handles raw dicts, lists, wrapped keys ('items', 'transactions'), and markdown fences.
    """
    clean_text = raw_text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", clean_text, flags=re.MULTILINE).strip()

    try:
        data = json.loads(clean_text)
    except Exception:
        return []

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    elif isinstance(data, dict):
        for key in ("transactions", "items", "data", "results"):
            if isinstance(data.get(key), list):
                return [item for item in data[key] if isinstance(item, dict)]
        return [data]
    return []


class AIService:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = api_key or settings.google_token
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self.model_name = model_name or settings.gemini_model

    async def classify_text(
        self,
        text: str,
        categories: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Classify text transaction into a list of items (batch processing).
        Returns: [{"category": str, "amount": float, "item_name": str, "type": "expense"|"income"}, ...]
        """
        if not self.client:
            return [{
                "category": categories[0] if categories else "Обязательные расходы",
                "type": "expense",
                "amount": None,
                "item_name": text
            }]

        prompt = (
            f"Ты финансовый ассистент приложения учёта бюджета Smart Bujet.\n"
            f"Определи ВСЕ позиции транзакций (расходы и доходы) из сообщения пользователя: \"{text}\".\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"Каждую позицию выдели отдельно. Название позиции (item_name) пиши с заглавной буквы.\n"
            f"Верни ответ строго в виде JSON-массива объектов со следующими полями:\n"
            f'[\n'
            f'  {{"category": "название из списка доступных", "type": "expense" или "income", "amount": число, "item_name": "Название позиции"}}\n'
            f']\n'
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
            return normalize_ai_json(response.text)
        except Exception as exc:
            logger.error("AI classify_text failed: %s", exc)
            return []

    async def parse_voice(
        self,
        audio_bytes: bytes,
        mime_type: str,
        categories: List[str]
    ) -> List[Dict[str, Any]]:
        """
        In-memory voice message processing via types.Part.from_bytes.
        Extracts all mentioned items.
        """
        if not self.client:
            return []

        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)
        prompt = (
            f"Прослушай аудиосообщение и выдели ВСЕ упомянутые расходы и доходы.\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"Каждую позицию выдели отдельно. Название каждой позиции (item_name) пиши с заглавной буквы.\n"
            f"Верни ответ строго в виде JSON-массива объектов со следующими полями:\n"
            f'[\n'
            f'  {{"category": "название из категорий", "type": "expense" или "income", "amount": число, "item_name": "Название позиции", "raw_text": "распознанный текст"}}\n'
            f']\n'
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
            return normalize_ai_json(response.text)
        except Exception as exc:
            logger.error("AI parse_voice failed: %s", exc)
            return []

    async def parse_receipt_photo(
        self,
        image_bytes: bytes,
        mime_type: str,
        categories: List[str]
    ) -> List[Dict[str, Any]]:
        """
        In-memory receipt photo processing via types.Part.from_bytes.
        Extracts receipt totals or items.
        """
        if not self.client:
            return []

        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        prompt = (
            f"Проанализируй фотографию чека/квитанции.\n"
            f"Доступные категории: {', '.join(categories)}.\n"
            f"Извлеки итоговую сумму или отдельные позиции чека. Название позиции (item_name) пиши с заглавной буквы.\n"
            f"Верни ответ строго в виде JSON-массива объектов:\n"
            f'[\n'
            f'  {{"category": "название из категорий", "type": "expense", "amount": число, "item_name": "Название магазина или товара"}}\n'
            f']\n'
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
            return normalize_ai_json(response.text)
        except Exception as exc:
            logger.error("AI parse_receipt_photo failed: %s", exc)
            return []

