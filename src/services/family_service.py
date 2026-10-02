import secrets
from typing import Optional, List
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.user import User
from src.models.family import FamilyGroup


class FamilyService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_group(self, owner_id: int, name: str) -> FamilyGroup:
        """Create a new family group with a unique invite code and set user as owner and member."""
        invite_code = secrets.token_urlsafe(8)
        group = FamilyGroup(
            name=name.strip(),
            owner_id=owner_id,
            invite_code=invite_code
        )
        self.session.add(group)
        await self.session.flush()

        user = await self.session.get(User, owner_id)
        if user:
            user.family_group_id = group.id

        await self.session.commit()
        await self.session.refresh(group)
        return group

    async def join_group(self, user_id: int, invite_code: str) -> Optional[FamilyGroup]:
        """Join an existing family group by invite code."""
        query = select(FamilyGroup).where(FamilyGroup.invite_code == invite_code.strip())
        group = await self.session.scalar(query)
        if not group:
            return None

        user = await self.session.get(User, user_id)
        if user:
            user.family_group_id = group.id
            await self.session.commit()
        return group

    async def leave_group(self, user_id: int) -> bool:
        """Leave current family group."""
        user = await self.session.get(User, user_id)
        if user and user.family_group_id:
            user.family_group_id = None
            await self.session.commit()
            return True
        return False

    async def get_group_members(self, group_id: UUID) -> List[User]:
        """Get all members of a family group."""
        query = select(User).where(User.family_group_id == group_id)
        result = await self.session.scalars(query)
        return result.all()

