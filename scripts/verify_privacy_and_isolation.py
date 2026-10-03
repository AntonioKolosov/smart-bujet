import asyncio
from src.core.database import async_session_maker
from src.models.user import User
from src.services.asset_service import AssetService
from src.services.family_service import FamilyService

async def main():
    async with async_session_maker() as session:
        anton = await session.get(User, 339914913)
        aiganym = await session.get(User, 378367224)

        asset_service = AssetService(session)
        family_service = FamilyService(session)

        # 1. Check personal assets isolation
        anton_assets = await asset_service.get_user_assets(anton.id)
        aiganym_assets = await asset_service.get_user_assets(aiganym.id)

        print(f"Anton personal assets count: {len(anton_assets)}")
        for a in anton_assets:
            t_val = getattr(a.type, 'value', str(a.type))
            print(f"  - Anton asset: {a.name} ({t_val}, {a.balance} {a.currency})")

        print(f"Aiganym personal assets count: {len(aiganym_assets)}")
        for a in aiganym_assets:
            t_val = getattr(a.type, 'value', str(a.type))
            print(f"  - Aiganym asset: {a.name} ({t_val}, {a.balance} {a.currency})")

        # Ensure no cross-contamination
        anton_asset_ids = {a.id for a in anton_assets}
        aiganym_asset_ids = {a.id for a in aiganym_assets}
        assert not (anton_asset_ids & aiganym_asset_ids), "Assets must not overlap!"

        # 2. Check family summary for Anton (single_member)
        anton_summary = await family_service.get_family_summary(anton)
        print(f"Anton family status: {anton_summary['status']}")
        assert anton_summary['status'] == 'single_member', f"Expected single_member, got {anton_summary['status']}"
        assert anton_summary['invite_link'] is not None, "Invite link must be present in single_member mode"

        # 3. Test deposit masking in family feed
        # Temporarily test get_family_transactions
        txs = await family_service.get_family_transactions(anton, limit=20)
        print(f"Anton feed tx count: {len(txs)}")
        for t in txs:
            print(f"  TX: title='{t['item_name']}', cat='{t['category_name']}', raw_text={t['raw_text']}")
            if any(k in (t['category_name'] or '').lower() for k in ['депозит', 'вклад']):
                assert t['item_name'] in ("Пополнение депозита", "Снятие с депозита", "Проценты по вкладу"), f"Item name was not masked: {t['item_name']}"
                assert t['raw_text'] is None, f"raw_text was not masked: {t['raw_text']}"

        print("\n>>> ALL PRIVACY & ISOLATION CHECKS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    asyncio.run(main())
