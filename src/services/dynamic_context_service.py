import logging
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.dynamic_context import DynamicFewShot
from src.models.alias import UserItemAlias

logger = logging.getLogger(__name__)

DEFAULT_FEW_SHOTS = [
    {
        "domain_tag": "debt",
        "raw_query": "друг вернул долг 50000",
        "expected_payload": {
            "is_financial": True,
            "items": [{
                "item_name": "Возврат долга",
                "amount": 50000,
                "type": "income",
                "category": "Денежный перевод"
            }]
        },
        "priority": 100,
    },
    {
        "domain_tag": "debt",
        "raw_query": "вернули долг 15000",
        "expected_payload": {
            "is_financial": True,
            "items": [{
                "item_name": "Возврат долга",
                "amount": 15000,
                "type": "income",
                "category": "Денежный перевод"
            }]
        },
        "priority": 90,
    },
    {
        "domain_tag": "debt",
        "raw_query": "вернул долг другу 50000",
        "expected_payload": {
            "is_financial": True,
            "items": [{
                "item_name": "Возврат долга другу",
                "amount": 50000,
                "type": "expense",
                "category": "Денежный перевод"
            }]
        },
        "priority": 90,
    },
    {
        "domain_tag": "debt",
        "raw_query": "дал в долг 20000",
        "expected_payload": {
            "is_financial": True,
            "items": [{
                "item_name": "Заём в долг",
                "amount": 20000,
                "type": "expense",
                "category": "Денежный перевод"
            }]
        },
        "priority": 80,
    },
    {
        "domain_tag": "debt",
        "raw_query": "взял в долг 30000",
        "expected_payload": {
            "is_financial": True,
            "items": [{
                "item_name": "Взял в долг",
                "amount": 30000,
                "type": "income",
                "category": "Денежный перевод"
            }]
        },
        "priority": 80,
    },
    {
        "domain_tag": "transfer",
        "raw_query": "перевела 14000",
        "expected_payload": {
            "is_financial": True,
            "items": [{
                "item_name": "Перевод",
                "amount": 14000,
                "type": "expense",
                "category": "Денежный перевод"
            }]
        },
        "priority": 80,
    },
    {
        "domain_tag": "food",
        "raw_query": "манты 9600",
        "expected_payload": {
            "is_financial": True,
            "items": [{
                "item_name": "Манты",
                "amount": 9600,
                "type": "expense",
                "category": "Продукты"
            }]
        },
        "priority": 80,
    },
]


class DynamicContextService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def seed_default_few_shots(self) -> None:
        """Seed default few-shots idempotently."""
        existing_count = await self.session.scalar(select(DynamicFewShot.id).limit(1))
        if existing_count is not None:
            return

        for item in DEFAULT_FEW_SHOTS:
            few_shot = DynamicFewShot(
                domain_tag=item["domain_tag"],
                raw_query=item["raw_query"],
                expected_payload=item["expected_payload"],
                priority=item["priority"],
                is_active=True,
            )
            self.session.add(few_shot)
        await self.session.commit()
        logger.info("Dynamic few-shots successfully seeded.")

    async def sanitize_poisoned_aliases(self) -> None:
        """Clean up previously poisoned aliases (e.g. debt return wrongly recorded as expense)."""
        await self.session.execute(
            delete(UserItemAlias).where(
                UserItemAlias.item_name_normalized.ilike("%друг вернул%")
                | UserItemAlias.item_name_normalized.ilike("%вернул долг%")
                | UserItemAlias.item_name_normalized.ilike("%возврат долга%")
            )
        )
        await self.session.commit()
        logger.info("Poisoned aliases sanitized.")

    async def get_few_shots_for_query(self, text: str) -> list[dict]:
        """Retrieve relevant few-shot examples based on keywords or tags."""
        t = text.lower()
        tags = []
        if any(w in t for w in ["долг", "занял", "одолжил", "вернул", "отдал", "заем", "возврат"]):
            tags.append("debt")
        if any(w in t for w in ["перевел", "перевела", "скинул", "скинула", "отправил", "отправила"]):
            tags.append("transfer")
        if any(w in t for w in ["манты", "пельмени", "плов", "шашлык", "мясо", "сыр", "колбаса"]):
            tags.append("food")

        query = select(DynamicFewShot).where(DynamicFewShot.is_active == True)
        if tags:
            query = query.where(DynamicFewShot.domain_tag.in_(tags))
        query = query.order_by(DynamicFewShot.priority.desc()).limit(4)

        results = (await self.session.scalars(query)).all()
        return [{"query": s.raw_query, "expected": s.expected_payload} for s in results]

    def format_few_shots_prompt(self, few_shots: list[dict]) -> str:
        if not few_shots:
            return ""
        lines = ["\nЭТАЛОННЫЕ ПРИМЕРЫ КЛАССИФИКАЦИИ:"]
        for s in few_shots:
            lines.append(f"- Вход: \"{s['query']}\" -> Результат: {s['expected']}")
        return "\n".join(lines) + "\n"
