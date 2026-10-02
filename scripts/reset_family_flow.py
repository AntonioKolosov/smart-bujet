import asyncio
from src.core.database import async_session_maker
from src.models.user import User
from src.models.family import FamilyGroup
from src.services.family_service import FamilyService
from sqlalchemy import select

async def main():
    async with async_session_maker() as session:
        # Find users
        users = (await session.scalars(select(User))).all()
        for u in users:
            print(f"User: {u.id}, name: {u.first_name}, family_group_id: {u.family_group_id}")

        # Detach Aiganym (id != 339914913) into her own solo group or nullify so Anton (339914913) is strictly solo
        anton = await session.get(User, 339914913)
        fam_service = FamilyService(session)
        anton_group = await fam_service.get_or_create_user_family(anton)
        print(f"Anton group: {anton_group.id}, code: {anton_group.invite_code}")

        # Detach any other user from Anton's group
        other_users = (await session.scalars(
            select(User).where(User.family_group_id == anton_group.id, User.id != anton.id)
        )).all()

        for other_u in other_users:
            print(f"Detaching {other_u.first_name} ({other_u.id}) from Anton's group...")
            other_u.family_group_id = None
            await session.flush()
            # Give other user their own group
            other_group = await fam_service.get_or_create_user_family(other_u)
            print(f"Assigned {other_u.first_name} to their own group: {other_group.id}, code: {other_group.invite_code}")

        await session.commit()

        # Verify Anton's family summary
        summary = await fam_service.get_family_summary(anton)
        print("=== Anton Family Summary ===")
        print(f"Status: {summary['status']}")
        print(f"Member count: {summary['member_count']}")
        print(f"Invite link: {summary['invite_link']}")
        print(f"Members: {[m['first_name'] for m in summary['members']]}")

if __name__ == "__main__":
    asyncio.run(main())
