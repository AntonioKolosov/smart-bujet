from typing import Sequence
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.category import Category, CategoryType

DEFAULT_CATEGORIES = [
    ("Продукты", CategoryType.expense),
    ("Еда вне дома", CategoryType.expense),
    ("Ребёнок", CategoryType.expense),
    ("Транспорт", CategoryType.expense),
    ("Здоровье", CategoryType.expense),
    ("Обязательные расходы", CategoryType.expense),
    ("Питомец", CategoryType.expense),
    ("Развлечения", CategoryType.expense),
    ("Образование", CategoryType.expense),
    ("Подписки", CategoryType.expense),
    ("Ремонт", CategoryType.expense),
    ("Шоппинг", CategoryType.expense),
    ("Прочее", CategoryType.expense),
    ("Зарплата", CategoryType.income),
    ("Подарок", CategoryType.expense),
    ("Денежный перевод", CategoryType.expense),
    ("Денежный перевод", CategoryType.income),
    ("Денежный перевод", CategoryType.transfer_out),
    ("Денежный перевод", CategoryType.transfer_in),
    ("Депозит и вклады", CategoryType.transfer_out),
    ("Снятие с депозита", CategoryType.transfer_in),
    ("Проценты по вкладу", CategoryType.income),
    ("Погашение кредита", CategoryType.expense),
    ("Получение кредита", CategoryType.income),
]


class CategoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def seed_default_categories(self) -> None:
        """Idempotently seed default system categories."""
        existing_res = await self.session.scalars(
            select(Category).where(Category.is_system == True)
        )
        existing = {(cat.name.lower(), cat.type) for cat in existing_res.all()}

        to_add = [
            Category(name=name, type=cat_type, is_system=True, user_id=None)
            for name, cat_type in DEFAULT_CATEGORIES
            if (name.lower(), cat_type) not in existing
        ]

        if to_add:
            self.session.add_all(to_add)
            await self.session.commit()

    async def get_categories(
        self,
        user_id: int | None = None,
        cat_type: CategoryType | None = None
    ) -> Sequence[Category]:
        """Fetch system categories and user-specific custom categories."""
        conditions = [
            or_(Category.is_system == True, Category.user_id == user_id)
        ]
        if cat_type:
            conditions.append(Category.type == cat_type)

        query = select(Category).where(and_(*conditions)).order_by(Category.name)
        result = await self.session.scalars(query)
        return result.all()

    async def find_by_name(
        self,
        name: str,
        cat_type: CategoryType | None = None,
        user_id: int | None = None
    ) -> Category | None:
        """Find category by name (case-insensitive) prioritizing user over system."""
        conditions = [
            Category.name.ilike(name.strip()),
            or_(Category.is_system == True, Category.user_id == user_id)
        ]
        if cat_type:
            conditions.append(Category.type == cat_type)

        query = (
            select(Category)
            .where(and_(*conditions))
            .order_by(Category.user_id.is_(None))  # user custom category first
        )
        return await self.session.scalar(query)

