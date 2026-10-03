DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> migrations/env.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import asyncio
   from logging.config import fileConfig
   import os


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> scripts/init_db.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import asyncio
   from src.core.database import engine, async_session_maker
   from src.models import Base
   from src.services.category_service import CategoryService

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> scripts/reset_family_flow.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import asyncio
   from src.core.database import async_session_maker
   from src.models.user import User
   from src.models.family import FamilyGroup

```

DESCRIPTION -> `src.models.family.FamilyGroup` imported but unused
LOCATION -> scripts/reset_family_flow.py:4:31
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from src.core.database import async_session_maker
   from src.models.user import User
-> from src.models.family import FamilyGroup
   from src.services.family_service import FamilyService
   from sqlalchemy import select


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> scripts/run_reports.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import argparse
   import asyncio
   from sqlalchemy import select
   from src.core.database import async_session_maker

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> scripts/run_reports.py:40:20
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   await bot.send_message(chat_id=user.id, text=msg)
                   print(f"Sent {period} report to user {user.id}")
->             except Exception as e:
                   print(f"Failed to send report to user {user.id}: {e}")



```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> scripts/verify_privacy_and_isolation.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import asyncio
   from src.core.database import async_session_maker
   from src.models.user import User
   from src.services.asset_service import AssetService

```

DESCRIPTION -> Line with empty comment
LOCATION -> src/api/__init__.py:1:1
RATIONALE -> Rule PLR2044. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> #

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/deps.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import json
   from fastapi import Depends, HTTPException, status, Header
   from sqlalchemy.ext.asyncio import AsyncSession
   from sqlalchemy import select

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/deps.py:12:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def get_current_user(
       init_data: str = Header(..., alias="X-Telegram-Init-Data"),
->     session: AsyncSession = Depends(get_db)
   ) -> User:
       validated = validate_init_data(init_data, settings.bot_token)
       if not validated or "user" not in validated:

```

DESCRIPTION -> Line with empty comment
LOCATION -> src/api/v1/__init__.py:1:1
RATIONALE -> Rule PLR2044. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> #

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/v1/analytics.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from fastapi import APIRouter, Depends, Query
   from sqlalchemy.ext.asyncio import AsyncSession
   from src.api.deps import get_db, get_current_user
   from src.schemas.analytics import ReportResponse

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/analytics.py:14:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       period: str = Query("month", description="Period: week, month, year"),
       include_family: bool = Query(False, description="Include family group transactions"),
->     session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       service = ReportService(session)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/analytics.py:15:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       include_family: bool = Query(False, description="Include family group transactions"),
       session: AsyncSession = Depends(get_db),
->     current_user: User = Depends(get_current_user)
   ):
       service = ReportService(session)
       family_id = current_user.family_group_id if include_family else None

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/v1/assets.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import uuid
   from typing import Optional, List
   from fastapi import APIRouter, Depends, HTTPException, status
   from pydantic import BaseModel

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/api/v1/assets.py:2:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import uuid
-> from typing import Optional, List
   from fastapi import APIRouter, Depends, HTTPException, status
   from pydantic import BaseModel
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> `typing.List` imported but unused
LOCATION -> src/api/v1/assets.py:2:30
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import uuid
-> from typing import Optional, List
   from fastapi import APIRouter, Depends, HTTPException, status
   from pydantic import BaseModel
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> `fastapi.status` imported but unused
LOCATION -> src/api/v1/assets.py:3:56
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import uuid
   from typing import Optional, List
-> from fastapi import APIRouter, Depends, HTTPException, status
   from pydantic import BaseModel
   from sqlalchemy.ext.asyncio import AsyncSession


```

DESCRIPTION -> `src.models.asset.AssetAccount` imported but unused
LOCATION -> src/api/v1/assets.py:9:30
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from src.api.deps import get_current_user, get_db
   from src.models.user import User
-> from src.models.asset import AssetAccount, AssetType
   from src.services.asset_service import AssetService

   router = APIRouter()

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/api/v1/assets.py:20:20
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       currency: str = "KZT"
       initial_balance: float = 0.0
->     interest_rate: Optional[float] = None


   class AssetActionRequest(BaseModel):

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/api/v1/assets.py:25:11
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   class AssetActionRequest(BaseModel):
       amount: float
->     note: Optional[str] = None


   @router.get("/")

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:30:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   @router.get("/")
   async def list_assets(
->     current_user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_db)
   ):
       service = AssetService(session)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:31:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def list_assets(
       current_user: User = Depends(get_current_user),
->     session: AsyncSession = Depends(get_db)
   ):
       service = AssetService(session)
       assets = await service.get_user_assets(current_user.id)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:52:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   @router.get("/summary")
   async def get_assets_summary(
->     current_user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_db)
   ):
       service = AssetService(session)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:53:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def get_assets_summary(
       current_user: User = Depends(get_current_user),
->     session: AsyncSession = Depends(get_db)
   ):
       service = AssetService(session)
       summary = await service.get_portfolio_summary(current_user.id)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:63:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def create_asset(
       payload: CreateAssetRequest,
->     current_user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_db)
   ):
       if not payload.name.strip():

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:64:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       payload: CreateAssetRequest,
       current_user: User = Depends(get_current_user),
->     session: AsyncSession = Depends(get_db)
   ):
       if not payload.name.strip():
           raise HTTPException(status_code=400, detail="Название актива обязательно")

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:95:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       asset_id: uuid.UUID,
       payload: AssetActionRequest,
->     current_user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_db)
   ):
       if payload.amount <= 0:

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:96:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       payload: AssetActionRequest,
       current_user: User = Depends(get_current_user),
->     session: AsyncSession = Depends(get_db)
   ):
       if payload.amount <= 0:
           raise HTTPException(status_code=400, detail="Сумма должна быть больше нуля")

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:122:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       asset_id: uuid.UUID,
       payload: AssetActionRequest,
->     current_user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_db)
   ):
       if payload.amount <= 0:

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:123:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       payload: AssetActionRequest,
       current_user: User = Depends(get_current_user),
->     session: AsyncSession = Depends(get_db)
   ):
       if payload.amount <= 0:
           raise HTTPException(status_code=400, detail="Сумма должна быть больше нуля")

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:147:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   @router.post("/accrue-interest")
   async def trigger_interest_accrual(
->     current_user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_db)
   ):
       """Accrue monthly interest across all active deposits for the user."""

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/assets.py:148:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def trigger_interest_accrual(
       current_user: User = Depends(get_current_user),
->     session: AsyncSession = Depends(get_db)
   ):
       """Accrue monthly interest across all active deposits for the user."""
       service = AssetService(session)

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/v1/auth.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import json
   from fastapi import APIRouter, HTTPException, status
   from pydantic import BaseModel
   from src.core.config import settings

```

DESCRIPTION -> `try`-`except`-`pass` detected, consider logging the exception
LOCATION -> src/api/v1/auth.py:25:9
RATIONALE -> Rule S110. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           try:
               user_info = json.loads(validated["user"])
->         except Exception:
               pass

       return {

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/api/v1/auth.py:25:16
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           try:
               user_info = json.loads(validated["user"])
->         except Exception:
               pass

       return {

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/v1/auth.py:35:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python


-> from fastapi import Depends
   from sqlalchemy.ext.asyncio import AsyncSession
   from src.api.deps import get_current_user, get_db
   from src.models.user import User

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/auth.py:43:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   @router.get("/me")
   async def get_me(
->     current_user: User = Depends(get_current_user),
       session: AsyncSession = Depends(get_db)
   ):
       tx_service = TransactionService(session)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/auth.py:44:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def get_me(
       current_user: User = Depends(get_current_user),
->     session: AsyncSession = Depends(get_db)
   ):
       tx_service = TransactionService(session)
       bal_data = await tx_service.get_user_balance(current_user.id)

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/api/v1/categories.py:1:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import List, Optional
   from fastapi import APIRouter, Depends, Query
   from sqlalchemy.ext.asyncio import AsyncSession
   from src.api.deps import get_db, get_current_user

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/v1/categories.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import List, Optional
   from fastapi import APIRouter, Depends, Query
   from sqlalchemy.ext.asyncio import AsyncSession
   from src.api.deps import get_db, get_current_user

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/api/v1/categories.py:12:33
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   router = APIRouter()

-> @router.get("/", response_model=List[CategoryRead])
   async def list_categories(
       type: Optional[str] = Query(None, description="Filter by type: income or expense"),
       session: AsyncSession = Depends(get_db),

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/api/v1/categories.py:14:11
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   @router.get("/", response_model=List[CategoryRead])
   async def list_categories(
->     type: Optional[str] = Query(None, description="Filter by type: income or expense"),
       session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/categories.py:15:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def list_categories(
       type: Optional[str] = Query(None, description="Filter by type: income or expense"),
->     session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       service = CategoryService(session)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/categories.py:16:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       type: Optional[str] = Query(None, description="Filter by type: income or expense"),
       session: AsyncSession = Depends(get_db),
->     current_user: User = Depends(get_current_user)
   ):
       service = CategoryService(session)
       cat_type = CategoryType(type) if type in CategoryType._value2member_map_ else None

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/categories.py:25:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def create_category(
       data: CategoryCreate,
->     session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       category = Category(

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/categories.py:26:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       data: CategoryCreate,
       session: AsyncSession = Depends(get_db),
->     current_user: User = Depends(get_current_user)
   ):
       category = Category(
           name=data.name.strip(),

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/v1/family.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import logging
   from typing import List, Optional
   from fastapi import APIRouter, Depends, HTTPException, status, Query
   from pydantic import BaseModel

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/api/v1/family.py:2:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import logging
-> from typing import List, Optional
   from fastapi import APIRouter, Depends, HTTPException, status, Query
   from pydantic import BaseModel
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> `typing.Optional` imported but unused
LOCATION -> src/api/v1/family.py:2:26
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import logging
-> from typing import List, Optional
   from fastapi import APIRouter, Depends, HTTPException, status, Query
   from pydantic import BaseModel
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> `src.schemas.family.FamilyGroupRead` imported but unused
LOCATION -> src/api/v1/family.py:10:78
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from src.models.user import User
   from src.services.family_service import FamilyService
-> from src.schemas.family import FamilySummaryResponse, FamilyTransactionItem, FamilyGroupRead
   from src.bot.bot import bot

   logger = logging.getLogger(__name__)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/family.py:23:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   @router.get("/summary", response_model=FamilySummaryResponse)
   async def get_family_summary(
->     session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       service = FamilyService(session)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/family.py:24:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def get_family_summary(
       session: AsyncSession = Depends(get_db),
->     current_user: User = Depends(get_current_user)
   ):
       service = FamilyService(session)
       return await service.get_family_summary(current_user)

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/api/v1/family.py:30:45
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python


-> @router.get("/transactions", response_model=List[FamilyTransactionItem])
   async def get_family_transactions(
       limit: int = Query(60, ge=1, le=100),
       offset: int = Query(0, ge=0),

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/family.py:34:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       limit: int = Query(60, ge=1, le=100),
       offset: int = Query(0, ge=0),
->     session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       service = FamilyService(session)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/family.py:35:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       offset: int = Query(0, ge=0),
       session: AsyncSession = Depends(get_db),
->     current_user: User = Depends(get_current_user)
   ):
       service = FamilyService(session)
       return await service.get_family_transactions(current_user, limit=limit, offset=offset)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/family.py:44:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def join_family_group(
       data: JoinFamilyRequest,
->     session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       service = FamilyService(session)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/family.py:45:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       data: JoinFamilyRequest,
       session: AsyncSession = Depends(get_db),
->     current_user: User = Depends(get_current_user)
   ):
       service = FamilyService(session)
       group, partner_id, msg = await service.join_by_invite(current_user, data.invite_code)

```

DESCRIPTION -> Use `f"@{current_user.username}"` instead of `f"@{current_user.username}" or ...`
LOCATION -> src/api/v1/family.py:54:55
RATIONALE -> Rule SIM222. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       if partner_id:
           try:
->             author_title = current_user.first_name or f"@{current_user.username}" or "Партнёр"
               await bot.send_message(
                   partner_id,
                   f"🎉 <b>{author_title}</b> присоединился(лась) к вашей семейной группе <b>«{group.name}»</b>!\n"

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/api/v1/family.py:60:16
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   f"Теперь ваши расходы и доходы синхронизированы в MiniApp."
               )
->         except Exception as exc:
               logger.warning("Failed to notify partner on join: %s", exc)

       return {"success": True, "message": msg, "group_name": group.name}

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/family.py:68:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   @router.post("/leave")
   async def leave_family_group(
->     session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       service = FamilyService(session)

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/family.py:69:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def leave_family_group(
       session: AsyncSession = Depends(get_db),
->     current_user: User = Depends(get_current_user)
   ):
       service = FamilyService(session)
       success, partner_id = await service.leave_group(current_user)

```

DESCRIPTION -> Use `f"@{current_user.username}"` instead of `f"@{current_user.username}" or ...`
LOCATION -> src/api/v1/family.py:78:55
RATIONALE -> Rule SIM222. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       if partner_id:
           try:
->             author_title = current_user.first_name or f"@{current_user.username}" or "Партнёр"
               await bot.send_message(
                   partner_id,
                   f"ℹ️ <b>{author_title}</b> покинул(а) семейную группу.\n"

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/api/v1/family.py:84:16
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   f"Семейный бюджет больше не синхронизируется."
               )
->         except Exception as exc:
               logger.warning("Failed to notify partner on leave: %s", exc)

       return {"success": True}

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/v1/router.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from fastapi import APIRouter
   from src.api.v1 import webhook, auth, transactions, categories, family, analytics, assets

   api_router = APIRouter()

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/api/v1/transactions.py:1:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import List, Optional
   from fastapi import APIRouter, Depends, Query
   from sqlalchemy import select, desc, or_
   from sqlalchemy.orm import joinedload

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/v1/transactions.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import List, Optional
   from fastapi import APIRouter, Depends, Query
   from sqlalchemy import select, desc, or_
   from sqlalchemy.orm import joinedload

```

DESCRIPTION -> `typing.Optional` imported but unused
LOCATION -> src/api/v1/transactions.py:1:26
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import List, Optional
   from fastapi import APIRouter, Depends, Query
   from sqlalchemy import select, desc, or_
   from sqlalchemy.orm import joinedload

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/api/v1/transactions.py:14:33
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   router = APIRouter()

-> @router.get("/", response_model=List[TransactionRead])
   async def list_transactions(
       include_family: bool = Query(False, description="Include family group transactions"),
       limit: int = Query(50, ge=1, le=200),

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/transactions.py:19:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       limit: int = Query(50, ge=1, le=200),
       offset: int = Query(0, ge=0),
->     session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       conditions = [Transaction.user_id == current_user.id]

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/transactions.py:20:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       offset: int = Query(0, ge=0),
       session: AsyncSession = Depends(get_db),
->     current_user: User = Depends(get_current_user)
   ):
       conditions = [Transaction.user_id == current_user.id]
       if include_family and current_user.family_group_id:

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/transactions.py:43:29
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def create_transaction(
       data: TransactionCreate,
->     session: AsyncSession = Depends(get_db),
       current_user: User = Depends(get_current_user)
   ):
       tx = Transaction(

```

DESCRIPTION -> Do not perform function call `Depends` in argument defaults; instead, perform the call within the function, or read the default from a module-level singleton variable
LOCATION -> src/api/v1/transactions.py:44:26
RATIONALE -> Rule B008. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       data: TransactionCreate,
       session: AsyncSession = Depends(get_db),
->     current_user: User = Depends(get_current_user)
   ):
       tx = Transaction(
           user_id=current_user.id,

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/api/v1/webhook.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from fastapi import APIRouter, Header, HTTPException, Request, status
   from aiogram.types import Update
   from src.bot.bot import dp, bot
   from src.core.config import settings

```

DESCRIPTION -> Line with empty comment
LOCATION -> src/bot/__init__.py:1:1
RATIONALE -> Rule PLR2044. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> #

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/bot/bot.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from aiogram import Bot, Dispatcher
   from aiogram.client.default import DefaultBotProperties
   from aiogram.enums import ParseMode
   from aiogram.utils.token import validate_token, TokenValidationError

```

DESCRIPTION -> `try`-`except`-`pass` detected, consider logging the exception
LOCATION -> src/bot/bot.py:17:5
RATIONALE -> Rule S110. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           if candidate and validate_token(candidate):
               return candidate
->     except (TokenValidationError, Exception):
           pass
       return DUMMY_FALLBACK_TOKEN


```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/bot/bot.py:17:35
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           if candidate and validate_token(candidate):
               return candidate
->     except (TokenValidationError, Exception):
           pass
       return DUMMY_FALLBACK_TOKEN


```

DESCRIPTION -> Line with empty comment
LOCATION -> src/bot/handlers/__init__.py:1:1
RATIONALE -> Rule PLR2044. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> #

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/bot/handlers/family.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from aiogram import Router
   from aiogram.filters import Command
   from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> `sqlalchemy.select` imported but unused
LOCATION -> src/bot/handlers/family.py:5:24
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
   from sqlalchemy.ext.asyncio import AsyncSession
-> from sqlalchemy import select
   from src.models.user import User
   from src.models.family import FamilyGroup
   from src.services.family_service import FamilyService

```

DESCRIPTION -> Use `f"@{user.username}"` instead of `f"@{user.username}" or ...`
LOCATION -> src/bot/handlers/family.py:72:51
RATIONALE -> Rule SIM222. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           if partner_id:
               try:
->                 author_title = user.first_name or f"@{user.username}" or "Партнёр"
                   await message.bot.send_message(
                       partner_id,
                       f"ℹ️ <b>{author_title}</b> покинул(а) семейную группу.\n"

```

DESCRIPTION -> `try`-`except`-`pass` detected, consider logging the exception
LOCATION -> src/bot/handlers/family.py:78:13
RATIONALE -> Rule S110. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                       f"Семейный бюджет больше не синхронизируется."
                   )
->             except Exception:
                   pass
           await message.reply("👋 Вы вышли из семейной группы.")
       else:

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/bot/handlers/family.py:78:20
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                       f"Семейный бюджет больше не синхронизируется."
                   )
->             except Exception:
                   pass
           await message.reply("👋 Вы вышли из семейной группы.")
       else:

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/bot/handlers/photo_tx.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import io
   import logging
   from aiogram import Router, F, Bot
   from aiogram.types import Message

```

DESCRIPTION -> Logging `.exception(...)` should be used instead of `.error(..., exc_info=True)`
LOCATION -> src/bot/handlers/photo_tx.py:56:16
RATIONALE -> Rule G201. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           await message.reply(BotMessages.photo_clarification())
       except Exception as exc:
->         logger.error("Error processing receipt photo: %s", exc, exc_info=True)
           await message.reply(BotMessages.service_unavailable())


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/bot/handlers/start.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from aiogram import Router, F
   from aiogram.filters import CommandStart, Command, CommandObject
   from aiogram.types import Message, CallbackQuery
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> `try`-`except`-`pass` detected, consider logging the exception
LOCATION -> src/bot/handlers/start.py:75:13
RATIONALE -> Rule S110. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                       f"Теперь ваши расходы и доходы объединены во вкладке «Семья» в MiniApp."
                   )
->             except Exception:
                   pass

           family_url = f"{get_miniapp_url()}?page=family"

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/bot/handlers/start.py:75:20
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                       f"Теперь ваши расходы и доходы объединены во вкладке «Семья» в MiniApp."
                   )
->             except Exception:
                   pass

           family_url = f"{get_miniapp_url()}?page=family"

```

DESCRIPTION -> Local variable `bal_data` is assigned to but never used
LOCATION -> src/bot/handlers/start.py:143:9
RATIONALE -> Rule F841. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           miniapp_url = get_miniapp_url()
           tx_service = TransactionService(session)
->         bal_data = await tx_service.get_user_balance(user_id)
           await callback.message.edit_text(
               BotMessages.currency_updated(currency),
               reply_markup=welcome_back_keyboard(miniapp_url=miniapp_url)

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/bot/handlers/text_tx.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import re
   import logging
   from aiogram import Router, F
   from aiogram.types import Message

```

DESCRIPTION -> Logging `.exception(...)` should be used instead of `.error(..., exc_info=True)`
LOCATION -> src/bot/handlers/text_tx.py:72:16
RATIONALE -> Rule G201. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           await message.reply(BotMessages.text_clarification())
       except Exception as exc:
->         logger.error("Error processing text transaction: %s", exc, exc_info=True)
           await message.reply(BotMessages.service_unavailable())


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/bot/handlers/voice_tx.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import io
   import logging
   from aiogram import Router, F, Bot
   from aiogram.types import Message

```

DESCRIPTION -> Logging `.exception(...)` should be used instead of `.error(..., exc_info=True)`
LOCATION -> src/bot/handlers/voice_tx.py:58:16
RATIONALE -> Rule G201. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           await message.reply(BotMessages.voice_clarification())
       except Exception as exc:
->         logger.error("Error processing voice transaction: %s", exc, exc_info=True)
           await message.reply(BotMessages.service_unavailable())


```

DESCRIPTION -> Line with empty comment
LOCATION -> src/bot/keyboards/__init__.py:1:1
RATIONALE -> Rule PLR2044. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> #

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/bot/keyboards/inline.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

   def currency_keyboard() -> InlineKeyboardMarkup:
       currencies = ["KZT", "RUB", "USD", "EUR"]

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/bot/messages.py:1:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import List, Union
   from src.models.transaction import Transaction
   from src.models.category import CategoryType


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/bot/messages.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import List, Union
   from src.models.transaction import Transaction
   from src.models.category import CategoryType


```

DESCRIPTION -> Use `X | Y` for type annotations
LOCATION -> src/bot/messages.py:28:23
RATIONALE -> Rule UP007. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       @staticmethod
       def tx_success(
->         transactions: Union[List[Transaction], Transaction],
           currency: str = "RUB",
           current_balance: float | None = None
       ) -> str:

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/bot/messages.py:28:29
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       @staticmethod
       def tx_success(
->         transactions: Union[List[Transaction], Transaction],
           currency: str = "RUB",
           current_balance: float | None = None
       ) -> str:

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/bot/messages.py:35:18
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               return "✅ <b>Записано!</b>"

->         tx_list: List[Transaction] = [transactions] if isinstance(transactions, Transaction) else transactions
           if not tx_list:
               return "✅ <b>Записано!</b>"


```

DESCRIPTION -> Line with empty comment
LOCATION -> src/bot/middlewares/__init__.py:1:1
RATIONALE -> Rule PLR2044. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> #

```

DESCRIPTION -> Import from `collections.abc` instead: `Callable`, `Awaitable`
LOCATION -> src/bot/middlewares/db_session.py:1:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import Callable, Dict, Any, Awaitable
   from aiogram import BaseMiddleware
   from aiogram.types import TelegramObject
   from src.core.database import async_session_maker

```

DESCRIPTION -> `typing.Dict` is deprecated, use `dict` instead
LOCATION -> src/bot/middlewares/db_session.py:1:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import Callable, Dict, Any, Awaitable
   from aiogram import BaseMiddleware
   from aiogram.types import TelegramObject
   from src.core.database import async_session_maker

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/bot/middlewares/db_session.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import Callable, Dict, Any, Awaitable
   from aiogram import BaseMiddleware
   from aiogram.types import TelegramObject
   from src.core.database import async_session_maker

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/bot/middlewares/db_session.py:9:44
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       async def __call__(
           self,
->         handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
           event: TelegramObject,
           data: Dict[str, Any]
       ) -> Any:

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/bot/middlewares/db_session.py:11:15
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
           event: TelegramObject,
->         data: Dict[str, Any]
       ) -> Any:
           async with async_session_maker() as session:
               data['session'] = session

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/core/accrual_scheduler.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import asyncio
   import calendar
   import logging
   from datetime import datetime, timezone

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/core/accrual_scheduler.py:5:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import logging
   from datetime import datetime, timezone
-> from typing import Optional, List

   from src.models.transaction import Transaction
   from src.services.asset_service import AssetService

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/core/accrual_scheduler.py:21:18
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   async def execute_accrual_check(
       session_maker,
->     target_date: Optional[datetime] = None
   ) -> List[Transaction]:
       """Execute monthly interest accrual across active deposit accounts."""
       async with session_maker() as session:

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/core/accrual_scheduler.py:22:6
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       session_maker,
       target_date: Optional[datetime] = None
-> ) -> List[Transaction]:
       """Execute monthly interest accrual across active deposit accounts."""
       async with session_maker() as session:
           service = AssetService(session)

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/core/accrual_scheduler.py:40:32
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       while True:
           try:
->             now = datetime.now(timezone.utc)
               # Accrue on the last day of the calendar month (28/29 in Feb, 30 or 31 in other months)
               if is_last_day_of_month(now):
                   await execute_accrual_check(session_maker, target_date=now)

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/core/accrual_scheduler.py:47:16
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               logger.info("Accrual background scheduler cancelled.")
               break
->         except Exception as exc:
               logger.error("Error in accrual background loop: %s", exc)

           try:

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/core/config.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import secrets
   from typing import Optional
   from pydantic import Field
   from pydantic_settings import BaseSettings, SettingsConfigDict

```

DESCRIPTION -> `typing.Optional` imported but unused
LOCATION -> src/core/config.py:2:20
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import secrets
-> from typing import Optional
   from pydantic import Field
   from pydantic_settings import BaseSettings, SettingsConfigDict


```

DESCRIPTION -> Import from `collections.abc` instead: `AsyncGenerator`
LOCATION -> src/core/database.py:1:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import AsyncGenerator

   from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/core/security.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import hashlib
   import hmac
   import time
   from urllib.parse import parse_qsl

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/core/security.py:32:12
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           return None
->     except Exception:
           return None

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/core/settings.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from src.core.config import settings, Settings

   __all__ = ["settings", "Settings"]


```

DESCRIPTION -> `__all__` is not sorted
LOCATION -> src/core/settings.py:3:11
RATIONALE -> Rule RUF022. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from src.core.config import settings, Settings

-> __all__ = ["settings", "Settings"]


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/main.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import asyncio
   import logging
   import os
   from contextlib import asynccontextmanager

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/main.py:67:16
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               ])
               logger.info("Chat menu button and bot commands successfully registered: %s", miniapp_url)
->         except Exception as exc:
               logger.warning("Could not set chat menu button or commands: %s", exc)

       # Start monthly deposit interest accrual background scheduler

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/models/__init__.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from src.models.base import Base
   from src.models.user import User
   from src.models.family import FamilyGroup
   from src.models.category import Category, CategoryType

```

DESCRIPTION -> `__all__` is not sorted
LOCATION -> src/models/__init__.py:9:11
RATIONALE -> Rule RUF022. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from src.models.asset import AssetAccount, AssetType

-> __all__ = [
       "Base",
       "User",
       "FamilyGroup",

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/models/alias.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from sqlalchemy import BigInteger, String, Integer, ForeignKey, UniqueConstraint
   from sqlalchemy.orm import Mapped, mapped_column, relationship

   from src.models.base import Base, TimestampMixin

```

DESCRIPTION -> Undefined name `User`
LOCATION -> src/models/alias.py:20:19
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       )

->     user: Mapped["User"] = relationship("User", back_populates="aliases")
       category: Mapped["Category"] = relationship("Category", back_populates="aliases")

```

DESCRIPTION -> Undefined name `Category`
LOCATION -> src/models/alias.py:21:23
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       user: Mapped["User"] = relationship("User", back_populates="aliases")
->     category: Mapped["Category"] = relationship("Category", back_populates="aliases")

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/models/asset.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import uuid
   from enum import Enum
   from typing import Optional


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/asset.py:27:27
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       currency: Mapped[str] = mapped_column(String(3), default="KZT")
       balance: Mapped[float] = mapped_column(Numeric(14, 2), default=0.0)
->     interest_rate: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
       is_active: Mapped[bool] = mapped_column(Boolean, default=True)

       user: Mapped["User"] = relationship("User", backref="asset_accounts")

```

DESCRIPTION -> Undefined name `User`
LOCATION -> src/models/asset.py:30:19
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       is_active: Mapped[bool] = mapped_column(Boolean, default=True)

->     user: Mapped["User"] = relationship("User", backref="asset_accounts")
       transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="asset_account")

```

DESCRIPTION -> Undefined name `Transaction`
LOCATION -> src/models/asset.py:31:32
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       user: Mapped["User"] = relationship("User", backref="asset_accounts")
->     transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="asset_account")

```

DESCRIPTION -> `typing.Annotated` imported but unused
LOCATION -> src/models/base.py:2:20
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime
-> from typing import Annotated

   from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
   from sqlalchemy.sql import func

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/models/category.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from enum import Enum
   from typing import Optional

   from sqlalchemy import Integer, String, BigInteger, Boolean, UniqueConstraint, ForeignKey

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/category.py:21:21
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
->     user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
       name: Mapped[str] = mapped_column(String(64))
       type: Mapped[CategoryType] = mapped_column()
       is_system: Mapped[bool] = mapped_column(Boolean, default=False)

```

DESCRIPTION -> Undefined name `Transaction`
LOCATION -> src/models/category.py:30:32
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       )

->     transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="category")
       aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="category")

```

DESCRIPTION -> Undefined name `UserItemAlias`
LOCATION -> src/models/category.py:31:27
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="category")
->     aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="category")

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/models/family.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import uuid
   from typing import Optional

   from sqlalchemy import String, ForeignKey, BigInteger

```

DESCRIPTION -> `typing.Optional` imported but unused
LOCATION -> src/models/family.py:2:20
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import uuid
-> from typing import Optional

   from sqlalchemy import String, ForeignKey, BigInteger
   from sqlalchemy.orm import Mapped, mapped_column, relationship

```

DESCRIPTION -> `sqlalchemy.dialects.postgresql.UUID` imported but unused
LOCATION -> src/models/family.py:6:52
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from sqlalchemy import String, ForeignKey, BigInteger
   from sqlalchemy.orm import Mapped, mapped_column, relationship
-> from sqlalchemy.dialects.postgresql import UUID as PGUUID

   from src.models.base import Base, TimestampMixin


```

DESCRIPTION -> Undefined name `User`
LOCATION -> src/models/family.py:19:20
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       invite_code: Mapped[str] = mapped_column(String(32), unique=True)

->     owner: Mapped["User"] = relationship("User", back_populates="owned_families", foreign_keys=[owner_id])
       members: Mapped[list["User"]] = relationship("User", back_populates="family_group", foreign_keys="[User.family_group_id]")
       transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="family_group")

```

DESCRIPTION -> Undefined name `User`
LOCATION -> src/models/family.py:20:27
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       owner: Mapped["User"] = relationship("User", back_populates="owned_families", foreign_keys=[owner_id])
->     members: Mapped[list["User"]] = relationship("User", back_populates="family_group", foreign_keys="[User.family_group_id]")
       transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="family_group")

```

DESCRIPTION -> Undefined name `Transaction`
LOCATION -> src/models/family.py:21:32
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       owner: Mapped["User"] = relationship("User", back_populates="owned_families", foreign_keys=[owner_id])
       members: Mapped[list["User"]] = relationship("User", back_populates="family_group", foreign_keys="[User.family_group_id]")
->     transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="family_group")

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/models/transaction.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import uuid
   from datetime import datetime
   from enum import Enum
   from typing import Optional

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:26:29
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
       user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
->     family_group_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("family_groups.id"))
       category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
       amount: Mapped[float] = mapped_column(Numeric(12, 2))
       original_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:29:29
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
       amount: Mapped[float] = mapped_column(Numeric(12, 2))
->     original_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
       discount_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
       type: Mapped[CategoryType] = mapped_column()
       asset_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("asset_accounts.id"), nullable=True)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:30:29
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       amount: Mapped[float] = mapped_column(Numeric(12, 2))
       original_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
->     discount_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
       type: Mapped[CategoryType] = mapped_column()
       asset_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("asset_accounts.id"), nullable=True)
       asset_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:32:30
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       discount_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
       type: Mapped[CategoryType] = mapped_column()
->     asset_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("asset_accounts.id"), nullable=True)
       asset_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
       exchange_rate: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
       related_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:33:26
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       type: Mapped[CategoryType] = mapped_column()
       asset_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("asset_accounts.id"), nullable=True)
->     asset_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
       exchange_rate: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
       related_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
       item_name: Mapped[Optional[str]] = mapped_column(String(255))

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:34:27
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       asset_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("asset_accounts.id"), nullable=True)
       asset_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
->     exchange_rate: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
       related_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
       item_name: Mapped[Optional[str]] = mapped_column(String(255))
       raw_text: Mapped[Optional[str]] = mapped_column(Text)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:35:36
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       asset_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
       exchange_rate: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
->     related_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
       item_name: Mapped[Optional[str]] = mapped_column(String(255))
       raw_text: Mapped[Optional[str]] = mapped_column(Text)
       source: Mapped[TransactionSource] = mapped_column()

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:36:23
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       exchange_rate: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
       related_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
->     item_name: Mapped[Optional[str]] = mapped_column(String(255))
       raw_text: Mapped[Optional[str]] = mapped_column(Text)
       source: Mapped[TransactionSource] = mapped_column()
       transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:37:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       related_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"), nullable=True)
       item_name: Mapped[Optional[str]] = mapped_column(String(255))
->     raw_text: Mapped[Optional[str]] = mapped_column(Text)
       source: Mapped[TransactionSource] = mapped_column()
       transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


```

DESCRIPTION -> Undefined name `User`
LOCATION -> src/models/transaction.py:41:19
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

->     user: Mapped["User"] = relationship("User", back_populates="transactions")
       family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="transactions")
       category: Mapped["Category"] = relationship("Category", back_populates="transactions")
       asset_account: Mapped[Optional["AssetAccount"]] = relationship("AssetAccount", back_populates="transactions")

```

DESCRIPTION -> Undefined name `FamilyGroup`
LOCATION -> src/models/transaction.py:42:36
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       user: Mapped["User"] = relationship("User", back_populates="transactions")
->     family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="transactions")
       category: Mapped["Category"] = relationship("Category", back_populates="transactions")
       asset_account: Mapped[Optional["AssetAccount"]] = relationship("AssetAccount", back_populates="transactions")
       related_transaction: Mapped[Optional["Transaction"]] = relationship("Transaction", remote_side="Transaction.id", foreign_keys=[related_transaction_id], post_update=True)

```

DESCRIPTION -> Undefined name `Category`
LOCATION -> src/models/transaction.py:43:23
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       user: Mapped["User"] = relationship("User", back_populates="transactions")
       family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="transactions")
->     category: Mapped["Category"] = relationship("Category", back_populates="transactions")
       asset_account: Mapped[Optional["AssetAccount"]] = relationship("AssetAccount", back_populates="transactions")
       related_transaction: Mapped[Optional["Transaction"]] = relationship("Transaction", remote_side="Transaction.id", foreign_keys=[related_transaction_id], post_update=True)


```

DESCRIPTION -> Undefined name `AssetAccount`
LOCATION -> src/models/transaction.py:44:37
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="transactions")
       category: Mapped["Category"] = relationship("Category", back_populates="transactions")
->     asset_account: Mapped[Optional["AssetAccount"]] = relationship("AssetAccount", back_populates="transactions")
       related_transaction: Mapped[Optional["Transaction"]] = relationship("Transaction", remote_side="Transaction.id", foreign_keys=[related_transaction_id], post_update=True)

       @property

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/transaction.py:48:32
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       @property
->     def category_name(self) -> Optional[str]:
           return self.category.name if self.category else None

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/models/user.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import Optional
   from uuid import UUID

   from sqlalchemy import BigInteger, String, Boolean, ForeignKey, Numeric

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/user.py:14:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
->     username: Mapped[Optional[str]] = mapped_column(String(64))
       first_name: Mapped[Optional[str]] = mapped_column(String(128))
       currency: Mapped[str] = mapped_column(String(3), default="KZT")
       initial_balance: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True, default=None)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/user.py:15:24
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
       username: Mapped[Optional[str]] = mapped_column(String(64))
->     first_name: Mapped[Optional[str]] = mapped_column(String(128))
       currency: Mapped[str] = mapped_column(String(3), default="KZT")
       initial_balance: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True, default=None)
       family_group_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("family_groups.id"))

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/user.py:17:29
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       first_name: Mapped[Optional[str]] = mapped_column(String(128))
       currency: Mapped[str] = mapped_column(String(3), default="KZT")
->     initial_balance: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True, default=None)
       family_group_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("family_groups.id"))
       is_active: Mapped[bool] = mapped_column(Boolean, default=True)


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/models/user.py:18:29
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       currency: Mapped[str] = mapped_column(String(3), default="KZT")
       initial_balance: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True, default=None)
->     family_group_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("family_groups.id"))
       is_active: Mapped[bool] = mapped_column(Boolean, default=True)

       transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")

```

DESCRIPTION -> Undefined name `Transaction`
LOCATION -> src/models/user.py:21:32
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       is_active: Mapped[bool] = mapped_column(Boolean, default=True)

->     transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
       aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="user")
       family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="members", foreign_keys=[family_group_id])
       owned_families: Mapped[list["FamilyGroup"]] = relationship("FamilyGroup", back_populates="owner", foreign_keys="[FamilyGroup.owner_id]")

```

DESCRIPTION -> Undefined name `UserItemAlias`
LOCATION -> src/models/user.py:22:27
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
->     aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="user")
       family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="members", foreign_keys=[family_group_id])
       owned_families: Mapped[list["FamilyGroup"]] = relationship("FamilyGroup", back_populates="owner", foreign_keys="[FamilyGroup.owner_id]")

```

DESCRIPTION -> Undefined name `FamilyGroup`
LOCATION -> src/models/user.py:23:36
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
       aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="user")
->     family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="members", foreign_keys=[family_group_id])
       owned_families: Mapped[list["FamilyGroup"]] = relationship("FamilyGroup", back_populates="owner", foreign_keys="[FamilyGroup.owner_id]")

```

DESCRIPTION -> Undefined name `FamilyGroup`
LOCATION -> src/models/user.py:24:34
RATIONALE -> Rule F821. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       aliases: Mapped[list["UserItemAlias"]] = relationship("UserItemAlias", back_populates="user")
       family_group: Mapped[Optional["FamilyGroup"]] = relationship("FamilyGroup", back_populates="members", foreign_keys=[family_group_id])
->     owned_families: Mapped[list["FamilyGroup"]] = relationship("FamilyGroup", back_populates="owner", foreign_keys="[FamilyGroup.owner_id]")

```

DESCRIPTION -> Line with empty comment
LOCATION -> src/schemas/__init__.py:1:1
RATIONALE -> Rule PLR2044. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> #

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/schemas/analytics.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from pydantic import BaseModel
   from typing import Dict, Any

   class ReportResponse(BaseModel):

```

DESCRIPTION -> `typing.Dict` is deprecated, use `dict` instead
LOCATION -> src/schemas/analytics.py:2:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from pydantic import BaseModel
-> from typing import Dict, Any

   class ReportResponse(BaseModel):
       total_expenses: str

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/schemas/analytics.py:8:14
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       total_income: str
       currency: str
->     details: Dict[str, Any] = {}

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/schemas/category.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from pydantic import BaseModel, ConfigDict
   from typing import Optional

   class CategoryCreate(BaseModel):

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/category.py:10:14
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   class CategoryRead(BaseModel):
       id: int
->     user_id: Optional[int] = None
       name: str
       type: str
       is_system: bool

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/schemas/family.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from datetime import datetime
   from typing import Optional, List
   from uuid import UUID
   from pydantic import BaseModel, ConfigDict

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/schemas/family.py:2:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime
-> from typing import Optional, List
   from uuid import UUID
   from pydantic import BaseModel, ConfigDict


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:22:17
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   class FamilyMemberInfo(BaseModel):
       id: int
->     first_name: Optional[str] = None
       username: Optional[str] = None
       currency: str = "KZT"
       current_balance: float = 0.0

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:23:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       id: int
       first_name: Optional[str] = None
->     username: Optional[str] = None
       currency: str = "KZT"
       current_balance: float = 0.0
       month_expense: float = 0.0

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:39:18
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       status: str  # "single_member" | "active_family"
       is_owner: bool
->     invite_code: Optional[str] = None
       invite_link: Optional[str] = None
       member_count: int
       combined_balance: float

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:40:18
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       is_owner: bool
       invite_code: Optional[str] = None
->     invite_link: Optional[str] = None
       member_count: int
       combined_balance: float
       combined_month_expense: float

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/schemas/family.py:47:14
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       currency: str
       month_period_name: str
->     members: List[FamilyMemberInfo]

       model_config = ConfigDict(from_attributes=True)


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:56:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       user_id: int
       author_name: str
->     author_username: Optional[str] = None
       is_current_user: bool
       amount: float
       original_amount: Optional[float] = None

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:59:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       is_current_user: bool
       amount: float
->     original_amount: Optional[float] = None
       discount_amount: Optional[float] = None
       type: str
       category_id: Optional[int] = None

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:60:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       amount: float
       original_amount: Optional[float] = None
->     discount_amount: Optional[float] = None
       type: str
       category_id: Optional[int] = None
       category_name: Optional[str] = None

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:62:18
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       discount_amount: Optional[float] = None
       type: str
->     category_id: Optional[int] = None
       category_name: Optional[str] = None
       item_name: Optional[str] = None
       raw_text: Optional[str] = None

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:63:20
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       type: str
       category_id: Optional[int] = None
->     category_name: Optional[str] = None
       item_name: Optional[str] = None
       raw_text: Optional[str] = None
       source: str

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:64:16
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       category_id: Optional[int] = None
       category_name: Optional[str] = None
->     item_name: Optional[str] = None
       raw_text: Optional[str] = None
       source: str
       transaction_date: datetime

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/family.py:65:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       category_name: Optional[str] = None
       item_name: Optional[str] = None
->     raw_text: Optional[str] = None
       source: str
       transaction_date: datetime


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/schemas/transaction.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from pydantic import BaseModel, ConfigDict
   from typing import Optional
   from decimal import Decimal
   from datetime import datetime

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/transaction.py:10:16
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       amount: Decimal
       category_id: int
->     item_name: Optional[str] = None
       type: str = "expense"
       raw_text: Optional[str] = None
       source: str = "manual"

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/transaction.py:12:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       item_name: Optional[str] = None
       type: str = "expense"
->     raw_text: Optional[str] = None
       source: str = "manual"
       transaction_date: Optional[datetime] = None


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/transaction.py:14:23
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       raw_text: Optional[str] = None
       source: str = "manual"
->     transaction_date: Optional[datetime] = None

   class TransactionRead(BaseModel):
       id: UUID

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/transaction.py:19:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       id: UUID
       user_id: int
->     family_group_id: Optional[UUID] = None
       category_id: int
       category_name: Optional[str] = None
       amount: Decimal

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/transaction.py:21:20
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       family_group_id: Optional[UUID] = None
       category_id: int
->     category_name: Optional[str] = None
       amount: Decimal
       original_amount: Optional[Decimal] = None
       discount_amount: Optional[Decimal] = None

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/transaction.py:23:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       category_name: Optional[str] = None
       amount: Decimal
->     original_amount: Optional[Decimal] = None
       discount_amount: Optional[Decimal] = None
       type: str
       item_name: Optional[str] = None

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/transaction.py:24:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       amount: Decimal
       original_amount: Optional[Decimal] = None
->     discount_amount: Optional[Decimal] = None
       type: str
       item_name: Optional[str] = None
       raw_text: Optional[str] = None

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/transaction.py:26:16
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       discount_amount: Optional[Decimal] = None
       type: str
->     item_name: Optional[str] = None
       raw_text: Optional[str] = None
       source: str
       transaction_date: datetime

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/transaction.py:27:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       type: str
       item_name: Optional[str] = None
->     raw_text: Optional[str] = None
       source: str
       transaction_date: datetime


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/schemas/user.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from pydantic import BaseModel, ConfigDict
   from typing import Optional
   from uuid import UUID


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/user.py:7:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   class UserCreate(BaseModel):
       id: int
->     username: Optional[str] = None
       first_name: Optional[str] = None
       currency: str = "RUB"


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/user.py:8:17
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       id: int
       username: Optional[str] = None
->     first_name: Optional[str] = None
       currency: str = "RUB"

   class UserRead(BaseModel):

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/user.py:13:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   class UserRead(BaseModel):
       id: int
->     username: Optional[str] = None
       first_name: Optional[str] = None
       currency: str = "RUB"
       family_group_id: Optional[UUID] = None

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/user.py:14:17
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       id: int
       username: Optional[str] = None
->     first_name: Optional[str] = None
       currency: str = "RUB"
       family_group_id: Optional[UUID] = None
       is_active: bool = True

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/schemas/user.py:16:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       first_name: Optional[str] = None
       currency: str = "RUB"
->     family_group_id: Optional[UUID] = None
       is_active: bool = True

       model_config = ConfigDict(from_attributes=True)

```

DESCRIPTION -> Line with empty comment
LOCATION -> src/services/__init__.py:1:1
RATIONALE -> Rule PLR2044. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> #

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/services/ai_service.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import json
   import logging
   import re
   from decimal import Decimal

```

DESCRIPTION -> `decimal.Decimal` imported but unused
LOCATION -> src/services/ai_service.py:4:21
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import logging
   import re
-> from decimal import Decimal
   from typing import Optional, Dict, Any, List
   from google import genai
   from google.genai import types

```

DESCRIPTION -> `typing.Dict` is deprecated, use `dict` instead
LOCATION -> src/services/ai_service.py:5:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import re
   from decimal import Decimal
-> from typing import Optional, Dict, Any, List
   from google import genai
   from google.genai import types
   from src.core.config import settings

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/services/ai_service.py:5:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import re
   from decimal import Decimal
-> from typing import Optional, Dict, Any, List
   from google import genai
   from google.genai import types
   from src.core.config import settings

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/ai_service.py:13:49
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python


-> def normalize_receipt_payload(raw_text: str) -> Dict[str, Any]:
       """
       Parses JSON from Gemini and returns a normalized payload:
       {

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/ai_service.py:29:12
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       try:
           data = json.loads(clean_text)
->     except Exception:
           return {"items": []}

       if isinstance(data, list):

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/ai_service.py:53:33
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

   class AIService:
->     def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
           self.api_key = api_key or settings.google_token
           self.client = genai.Client(api_key=self.api_key) if self.api_key else None
           self.model_name = model_name or settings.gemini_model

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/ai_service.py:53:67
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

   class AIService:
->     def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
           self.api_key = api_key or settings.google_token
           self.client = genai.Client(api_key=self.api_key) if self.api_key else None
           self.model_name = model_name or settings.gemini_model

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/ai_service.py:59:48
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       @staticmethod
->     def _format_assets_context(assets_context: Optional[List[Dict[str, Any]]]) -> str:
           if not assets_context:
               return ""
           lines = [

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/ai_service.py:59:57
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       @staticmethod
->     def _format_assets_context(assets_context: Optional[List[Dict[str, Any]]]) -> str:
           if not assets_context:
               return ""
           lines = [

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/ai_service.py:59:62
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       @staticmethod
->     def _format_assets_context(assets_context: Optional[List[Dict[str, Any]]]) -> str:
           if not assets_context:
               return ""
           lines = [

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/ai_service.py:75:21
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self,
           text: str,
->         categories: List[str],
           assets_context: Optional[List[Dict[str, Any]]] = None
       ) -> Dict[str, Any]:
           """Classify message into items and optional discount parameters."""

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/ai_service.py:76:25
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           text: str,
           categories: List[str],
->         assets_context: Optional[List[Dict[str, Any]]] = None
       ) -> Dict[str, Any]:
           """Classify message into items and optional discount parameters."""
           if not self.client:

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/ai_service.py:76:34
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           text: str,
           categories: List[str],
->         assets_context: Optional[List[Dict[str, Any]]] = None
       ) -> Dict[str, Any]:
           """Classify message into items and optional discount parameters."""
           if not self.client:

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/ai_service.py:76:39
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           text: str,
           categories: List[str],
->         assets_context: Optional[List[Dict[str, Any]]] = None
       ) -> Dict[str, Any]:
           """Classify message into items and optional discount parameters."""
           if not self.client:

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/ai_service.py:77:10
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           categories: List[str],
           assets_context: Optional[List[Dict[str, Any]]] = None
->     ) -> Dict[str, Any]:
           """Classify message into items and optional discount parameters."""
           if not self.client:
               return {

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/ai_service.py:126:16
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               )
               return normalize_receipt_payload(response.text)
->         except Exception as exc:
               logger.error("AI classify_text failed: %s", exc)
               return {"items": []}


```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/ai_service.py:134:21
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           audio_bytes: bytes,
           mime_type: str,
->         categories: List[str],
           assets_context: Optional[List[Dict[str, Any]]] = None
       ) -> Dict[str, Any]:
           """In-memory voice message processing with discount and income extraction."""

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/ai_service.py:135:25
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           mime_type: str,
           categories: List[str],
->         assets_context: Optional[List[Dict[str, Any]]] = None
       ) -> Dict[str, Any]:
           """In-memory voice message processing with discount and income extraction."""
           if not self.client:

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/ai_service.py:135:34
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           mime_type: str,
           categories: List[str],
->         assets_context: Optional[List[Dict[str, Any]]] = None
       ) -> Dict[str, Any]:
           """In-memory voice message processing with discount and income extraction."""
           if not self.client:

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/ai_service.py:135:39
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           mime_type: str,
           categories: List[str],
->         assets_context: Optional[List[Dict[str, Any]]] = None
       ) -> Dict[str, Any]:
           """In-memory voice message processing with discount and income extraction."""
           if not self.client:

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/ai_service.py:136:10
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           categories: List[str],
           assets_context: Optional[List[Dict[str, Any]]] = None
->     ) -> Dict[str, Any]:
           """In-memory voice message processing with discount and income extraction."""
           if not self.client:
               return {"items": []}

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/ai_service.py:178:16
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               )
               return normalize_receipt_payload(response.text)
->         except Exception as exc:
               logger.error("AI parse_voice failed: %s", exc)
               return {"items": []}


```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/ai_service.py:186:21
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           image_bytes: bytes,
           mime_type: str,
->         categories: List[str]
       ) -> Dict[str, Any]:
           """In-memory receipt photo processing with discount and total extraction."""
           if not self.client:

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/ai_service.py:187:10
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           mime_type: str,
           categories: List[str]
->     ) -> Dict[str, Any]:
           """In-memory receipt photo processing with discount and total extraction."""
           if not self.client:
               return {"items": []}

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/ai_service.py:220:16
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               )
               return normalize_receipt_payload(response.text)
->         except Exception as exc:
               logger.error("AI parse_receipt_photo failed: %s", exc)
               return {"items": []}


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/services/asset_service.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import re
   from datetime import datetime, timezone
   from decimal import Decimal, ROUND_HALF_UP
   from typing import List, Optional, Dict, Any

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/services/asset_service.py:4:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime, timezone
   from decimal import Decimal, ROUND_HALF_UP
-> from typing import List, Optional, Dict, Any
   import uuid

   from sqlalchemy import select

```

DESCRIPTION -> `typing.Dict` is deprecated, use `dict` instead
LOCATION -> src/services/asset_service.py:4:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime, timezone
   from decimal import Decimal, ROUND_HALF_UP
-> from typing import List, Optional, Dict, Any
   import uuid

   from sqlalchemy import select

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/asset_service.py:22:54
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self.category_service = CategoryService(session)

->     async def get_user_assets(self, user_id: int) -> List[AssetAccount]:
           """Fetch all active personal asset accounts for user (isolated to user only)."""
           res = await self.session.scalars(
               select(AssetAccount)

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/asset_service.py:31:60
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           return list(res.all())

->     async def get_accessible_assets(self, user_id: int) -> List[AssetAccount]:
           """Fetch active asset accounts for user (strictly personal)."""
           return await self.get_user_assets(user_id)


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:49:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self,
           user_id: int,
->         target_name: Optional[str] = None,
           target_type: Optional[AssetType] = None,
           target_currency: Optional[str] = None,
           asset_id_hint: Optional[str] = None

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:50:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           user_id: int,
           target_name: Optional[str] = None,
->         target_type: Optional[AssetType] = None,
           target_currency: Optional[str] = None,
           asset_id_hint: Optional[str] = None
       ) -> Optional[AssetAccount]:

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:51:26
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           target_name: Optional[str] = None,
           target_type: Optional[AssetType] = None,
->         target_currency: Optional[str] = None,
           asset_id_hint: Optional[str] = None
       ) -> Optional[AssetAccount]:
           """

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:52:24
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           target_type: Optional[AssetType] = None,
           target_currency: Optional[str] = None,
->         asset_id_hint: Optional[str] = None
       ) -> Optional[AssetAccount]:
           """
           Multi-tier deterministic and fuzzy matching for asset accounts:

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:53:10
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           target_currency: Optional[str] = None,
           asset_id_hint: Optional[str] = None
->     ) -> Optional[AssetAccount]:
           """
           Multi-tier deterministic and fuzzy matching for asset accounts:
           1. Exact UUID hint match.

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:130:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           asset_type: AssetType = AssetType.deposit,
           currency: str = "KZT",
->         name: Optional[str] = None
       ) -> AssetAccount:
           """Find an existing asset of matching type/currency or create a sensible default."""
           safe_currency = currency.strip().upper() if currency and currency.strip().upper() not in ("NONE", "NULL", "") else "KZT"

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:172:24
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           currency: str = "KZT",
           initial_balance: float = 0.0,
->         interest_rate: Optional[float] = None
       ) -> AssetAccount:
           account = AssetAccount(
               user_id=user_id,

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:192:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           asset_id: uuid.UUID,
           amount: float,
->         note: Optional[str] = None
       ) -> AssetAccount:
           """Transfer funds from main balance into asset account."""
           account = await self.session.get(AssetAccount, asset_id)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:228:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           asset_id: uuid.UUID,
           amount: float,
->         note: Optional[str] = None
       ) -> AssetAccount:
           """Withdraw funds from asset into main liquid balance."""
           account = await self.session.get(AssetAccount, asset_id)

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/asset_service.py:259:60
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           return account

->     async def get_portfolio_summary(self, user_id: int) -> Dict[str, Any]:
           """Aggregate total net worth: liquid balance + deposits + currencies."""
           accounts = await self.get_user_assets(user_id)
           user = await self.session.get(User, user_id)

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/asset_service.py:268:39
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           base_rate_to_kzt = approx_rates_to_kzt.get(base_currency, 1.0)

->         total_deposits_base = Decimal("0")
           total_currency_base = Decimal("0")
           account_list = []


```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/asset_service.py:269:39
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           total_deposits_base = Decimal("0")
->         total_currency_base = Decimal("0")
           account_list = []

           for acc in accounts:

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:305:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self,
           account: AssetAccount,
->         target_date: Optional[datetime] = None
       ) -> Optional[Transaction]:
           """Accrues monthly interest for a single deposit account with strict idempotency."""
           if account.type != AssetType.deposit or not account.interest_rate or account.interest_rate <= 0:

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:306:10
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           account: AssetAccount,
           target_date: Optional[datetime] = None
->     ) -> Optional[Transaction]:
           """Accrues monthly interest for a single deposit account with strict idempotency."""
           if account.type != AssetType.deposit or not account.interest_rate or account.interest_rate <= 0:
               return None

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/asset_service.py:313:43
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               return None

->         now = target_date or datetime.now(timezone.utc)
           start_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
           if now.month == 12:
               end_of_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/asset_service.py:314:75
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           now = target_date or datetime.now(timezone.utc)
->         start_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
           if now.month == 12:
               end_of_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
           else:

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/asset_service.py:316:73
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           start_of_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
           if now.month == 12:
->             end_of_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
           else:
               end_of_month = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)


```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/asset_service.py:318:81
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               end_of_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
           else:
->             end_of_month = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

           # 1. Resolve interest category
           interest_cat = await self.category_service.find_by_name(

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/asset_service.py:347:66
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           # 3. Calculation with Decimal precision: annual rate / 12
           bal_dec = Decimal(str(account.balance))
->         rate_dec = Decimal(str(account.interest_rate)) / Decimal("100")
           monthly_interest = (bal_dec * rate_dec / Decimal("12")).quantize(
               Decimal("0.01"), rounding=ROUND_HALF_UP
           )

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/asset_service.py:348:58
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           bal_dec = Decimal(str(account.balance))
           rate_dec = Decimal(str(account.interest_rate)) / Decimal("100")
->         monthly_interest = (bal_dec * rate_dec / Decimal("12")).quantize(
               Decimal("0.01"), rounding=ROUND_HALF_UP
           )


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:382:18
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       async def accrue_monthly_interest_for_all(
           self,
->         user_id: Optional[int] = None,
           target_date: Optional[datetime] = None
       ) -> List[Transaction]:
           """Runs interest accrual across active deposits with interest rates."""

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/asset_service.py:383:22
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self,
           user_id: Optional[int] = None,
->         target_date: Optional[datetime] = None
       ) -> List[Transaction]:
           """Runs interest accrual across active deposits with interest rates."""
           query = select(AssetAccount).where(

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/asset_service.py:384:10
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           user_id: Optional[int] = None,
           target_date: Optional[datetime] = None
->     ) -> List[Transaction]:
           """Runs interest accrual across active deposits with interest rates."""
           query = select(AssetAccount).where(
               AssetAccount.type == AssetType.deposit,

```

DESCRIPTION -> Import from `collections.abc` instead: `Sequence`
LOCATION -> src/services/category_service.py:1:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import Optional, Sequence
   from sqlalchemy import select, and_, or_
   from sqlalchemy.ext.asyncio import AsyncSession
   from src.models.category import Category, CategoryType

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/services/category_service.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from typing import Optional, Sequence
   from sqlalchemy import select, and_, or_
   from sqlalchemy.ext.asyncio import AsyncSession
   from src.models.category import Category, CategoryType

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/category_service.py:52:18
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       async def get_categories(
           self,
->         user_id: Optional[int] = None,
           cat_type: Optional[CategoryType] = None
       ) -> Sequence[Category]:
           """Fetch system categories and user-specific custom categories."""

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/category_service.py:53:19
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self,
           user_id: Optional[int] = None,
->         cat_type: Optional[CategoryType] = None
       ) -> Sequence[Category]:
           """Fetch system categories and user-specific custom categories."""
           conditions = [

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/category_service.py:69:19
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self,
           name: str,
->         cat_type: Optional[CategoryType] = None,
           user_id: Optional[int] = None
       ) -> Optional[Category]:
           """Find category by name (case-insensitive) prioritizing user over system."""

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/category_service.py:70:18
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           name: str,
           cat_type: Optional[CategoryType] = None,
->         user_id: Optional[int] = None
       ) -> Optional[Category]:
           """Find category by name (case-insensitive) prioritizing user over system."""
           conditions = [

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/category_service.py:71:10
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           cat_type: Optional[CategoryType] = None,
           user_id: Optional[int] = None
->     ) -> Optional[Category]:
           """Find category by name (case-insensitive) prioritizing user over system."""
           conditions = [
               Category.name.ilike(name.strip()),

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/services/discount_service.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
   from typing import List, Dict, Any, Optional



```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/services/discount_service.py:2:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
-> from typing import List, Dict, Any, Optional


   class DiscountDistributor:

```

DESCRIPTION -> `typing.Dict` is deprecated, use `dict` instead
LOCATION -> src/services/discount_service.py:2:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
-> from typing import List, Dict, Any, Optional


   class DiscountDistributor:

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/discount_service.py:8:16
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       @staticmethod
       def distribute(
->         items: List[Dict[str, Any]],
           discount_percent: Optional[float] = None,
           discount_amount: Optional[float] = None,
           total_paid: Optional[float] = None,

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/discount_service.py:8:21
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       @staticmethod
       def distribute(
->         items: List[Dict[str, Any]],
           discount_percent: Optional[float] = None,
           discount_amount: Optional[float] = None,
           total_paid: Optional[float] = None,

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/discount_service.py:9:27
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       def distribute(
           items: List[Dict[str, Any]],
->         discount_percent: Optional[float] = None,
           discount_amount: Optional[float] = None,
           total_paid: Optional[float] = None,
       ) -> List[Dict[str, Any]]:

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/discount_service.py:10:26
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           items: List[Dict[str, Any]],
           discount_percent: Optional[float] = None,
->         discount_amount: Optional[float] = None,
           total_paid: Optional[float] = None,
       ) -> List[Dict[str, Any]]:
           """

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/discount_service.py:11:21
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           discount_percent: Optional[float] = None,
           discount_amount: Optional[float] = None,
->         total_paid: Optional[float] = None,
       ) -> List[Dict[str, Any]]:
           """
           Deterministically distributes discount across expense items using the Largest Remainder Method (Hamilton Algorithm).

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/discount_service.py:12:10
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           discount_amount: Optional[float] = None,
           total_paid: Optional[float] = None,
->     ) -> List[Dict[str, Any]]:
           """
           Deterministically distributes discount across expense items using the Largest Remainder Method (Hamilton Algorithm).
           Reconciles every penny/tiyn so sum(item.amount) == total_paid.

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/discount_service.py:12:15
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           discount_amount: Optional[float] = None,
           total_paid: Optional[float] = None,
->     ) -> List[Dict[str, Any]]:
           """
           Deterministically distributes discount across expense items using the Largest Remainder Method (Hamilton Algorithm).
           Reconciles every penny/tiyn so sum(item.amount) == total_paid.

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:23:112
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           expense_indices = [
               i for i, item in enumerate(items)
->             if item.get("type", "expense") == "expense" and Decimal(str(item.get("amount", 0) or 0)) > Decimal("0")
           ]

           if not expense_indices:

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:33:32
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           # Determine target discount
->         discount_val = Decimal("0")

           if total_paid is not None:
               try:

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:38:28
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               try:
                   t_paid = Decimal(str(total_paid))
->                 if Decimal("0") < t_paid < base_sum:
                       discount_val = base_sum - t_paid
               except Exception:
                   pass

```

DESCRIPTION -> `try`-`except`-`pass` detected, consider logging the exception
LOCATION -> src/services/discount_service.py:40:13
RATIONALE -> Rule S110. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   if Decimal("0") < t_paid < base_sum:
                       discount_val = base_sum - t_paid
->             except Exception:
                   pass

           if discount_val <= Decimal("0") and discount_amount is not None:

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/discount_service.py:40:20
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   if Decimal("0") < t_paid < base_sum:
                       discount_val = base_sum - t_paid
->             except Exception:
                   pass

           if discount_val <= Decimal("0") and discount_amount is not None:

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:43:36
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   pass

->         if discount_val <= Decimal("0") and discount_amount is not None:
               try:
                   d_amt = Decimal(str(discount_amount))
                   if Decimal("0") < d_amt < base_sum:

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:46:28
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               try:
                   d_amt = Decimal(str(discount_amount))
->                 if Decimal("0") < d_amt < base_sum:
                       discount_val = d_amt
               except Exception:
                   pass

```

DESCRIPTION -> `try`-`except`-`pass` detected, consider logging the exception
LOCATION -> src/services/discount_service.py:48:13
RATIONALE -> Rule S110. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   if Decimal("0") < d_amt < base_sum:
                       discount_val = d_amt
->             except Exception:
                   pass

           if discount_val <= Decimal("0") and discount_percent is not None:

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/discount_service.py:48:20
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   if Decimal("0") < d_amt < base_sum:
                       discount_val = d_amt
->             except Exception:
                   pass

           if discount_val <= Decimal("0") and discount_percent is not None:

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:51:36
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   pass

->         if discount_val <= Decimal("0") and discount_percent is not None:
               try:
                   pct = Decimal(str(discount_percent))
                   if Decimal("0") < pct < Decimal("100"):

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:54:28
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               try:
                   pct = Decimal(str(discount_percent))
->                 if Decimal("0") < pct < Decimal("100"):
                       discount_val = (base_sum * (pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
               except Exception:
                   pass

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:54:49
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               try:
                   pct = Decimal(str(discount_percent))
->                 if Decimal("0") < pct < Decimal("100"):
                       discount_val = (base_sum * (pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
               except Exception:
                   pass

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:55:63
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   pct = Decimal(str(discount_percent))
                   if Decimal("0") < pct < Decimal("100"):
->                     discount_val = (base_sum * (pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
               except Exception:
                   pass


```

DESCRIPTION -> `try`-`except`-`pass` detected, consider logging the exception
LOCATION -> src/services/discount_service.py:56:13
RATIONALE -> Rule S110. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   if Decimal("0") < pct < Decimal("100"):
                       discount_val = (base_sum * (pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
->             except Exception:
                   pass

           if discount_val <= Decimal("0"):

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/discount_service.py:56:20
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   if Decimal("0") < pct < Decimal("100"):
                       discount_val = (base_sum * (pct / Decimal("100"))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
->             except Exception:
                   pass

           if discount_val <= Decimal("0"):

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:59:36
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   pass

->         if discount_val <= Decimal("0"):
               return items

           # Largest Remainder Method

```

DESCRIPTION -> Local variable `exact_discounts` is assigned to but never used
LOCATION -> src/services/discount_service.py:63:9
RATIONALE -> Rule F841. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           # Largest Remainder Method
->         exact_discounts = []
           floor_discounts = []
           remainders = []


```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:70:42
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               item_amt = Decimal(str(items[idx].get("amount", 0)))
               exact_d = discount_val * (item_amt / base_sum)
->             floor_d = (exact_d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_FLOOR) / Decimal("100")
               rem = exact_d - floor_d

               floor_discounts.append(floor_d)

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:70:67
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               item_amt = Decimal(str(items[idx].get("amount", 0)))
               exact_d = discount_val * (item_amt / base_sum)
->             floor_d = (exact_d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_FLOOR) / Decimal("100")
               rem = exact_d - floor_d

               floor_discounts.append(floor_d)

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:70:105
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               item_amt = Decimal(str(items[idx].get("amount", 0)))
               exact_d = discount_val * (item_amt / base_sum)
->             floor_d = (exact_d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_FLOOR) / Decimal("100")
               rem = exact_d - floor_d

               floor_discounts.append(floor_d)

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:77:76
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           allocated_base = sum(floor_discounts)
->         unallocated_cents = int(((discount_val - allocated_base) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

           # Sort remainders descending by remainder, then by item amount
           remainders.sort(key=lambda x: (x[0], x[1]), reverse=True)

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:77:101
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           allocated_base = sum(floor_discounts)
->         unallocated_cents = int(((discount_val - allocated_base) * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

           # Sort remainders descending by remainder, then by item amount
           remainders.sort(key=lambda x: (x[0], x[1]), reverse=True)

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/discount_service.py:82:26
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           remainders.sort(key=lambda x: (x[0], x[1]), reverse=True)

->         final_discounts: Dict[int, Decimal] = {}
           for rank, (rem, item_amt, idx) in enumerate(remainders):
               bonus = Decimal("0.01") if rank < unallocated_cents else Decimal("0")
               item_pos = expense_indices.index(idx)

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/discount_service.py:84:78
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           final_discounts: Dict[int, Decimal] = {}
           for rank, (rem, item_amt, idx) in enumerate(remainders):
->             bonus = Decimal("0.01") if rank < unallocated_cents else Decimal("0")
               item_pos = expense_indices.index(idx)
               final_discounts[idx] = floor_discounts[item_pos] + bonus


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/services/family_service.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import secrets
   import logging
   from datetime import datetime, timezone
   from typing import Optional, List, Tuple

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/services/family_service.py:4:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import logging
   from datetime import datetime, timezone
-> from typing import Optional, List, Tuple
   from uuid import UUID
   from sqlalchemy import select, or_, desc, func
   from sqlalchemy.orm import joinedload

```

DESCRIPTION -> `typing.Tuple` is deprecated, use `tuple` instead
LOCATION -> src/services/family_service.py:4:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import logging
   from datetime import datetime, timezone
-> from typing import Optional, List, Tuple
   from uuid import UUID
   from sqlalchemy import select, or_, desc, func
   from sqlalchemy.orm import joinedload

```

DESCRIPTION -> `uuid.UUID` imported but unused
LOCATION -> src/services/family_service.py:5:18
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime, timezone
   from typing import Optional, List, Tuple
-> from uuid import UUID
   from sqlalchemy import select, or_, desc, func
   from sqlalchemy.orm import joinedload
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/family_service.py:71:18
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           )
           members_res = await self.session.scalars(members_query)
->         members: List[User] = members_res.all()

           members_info = []
           combined_balance = 0.0

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/family_service.py:107:28
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           # Intercompany elimination: exclude intra-family transfers from combined external family cashflow
->         now = datetime.now(timezone.utc)
           start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
           if now.month == 12:
               next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/family_service.py:108:72
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           # Intercompany elimination: exclude intra-family transfers from combined external family cashflow
           now = datetime.now(timezone.utc)
->         start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
           if now.month == 12:
               next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
           else:

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/family_service.py:110:71
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
           if now.month == 12:
->             next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
           else:
               next_month = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)


```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/family_service.py:112:79
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
           else:
->             next_month = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

           intra_family_expense = await self.session.scalar(
               select(func.coalesce(func.sum(Transaction.amount), 0))

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/family_service.py:155:94
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           }

->     async def get_family_transactions(self, user: User, limit: int = 60, offset: int = 0) -> List[dict]:
           """
           Joint Feed:
           Fetches all transactions for family members with author badges without N+1 overhead.

```

DESCRIPTION -> Use `tuple` instead of `Tuple` for type annotation
LOCATION -> src/services/family_service.py:227:69
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           return result

->     async def join_by_invite(self, user: User, invite_code: str) -> Tuple[Optional[FamilyGroup], Optional[int], str]:
           """
           Joins an existing group by deep-link invite code.
           Returns: (group, partner_id_to_notify, message)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/family_service.py:227:75
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           return result

->     async def join_by_invite(self, user: User, invite_code: str) -> Tuple[Optional[FamilyGroup], Optional[int], str]:
           """
           Joins an existing group by deep-link invite code.
           Returns: (group, partner_id_to_notify, message)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/family_service.py:227:98
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           return result

->     async def join_by_invite(self, user: User, invite_code: str) -> Tuple[Optional[FamilyGroup], Optional[int], str]:
           """
           Joins an existing group by deep-link invite code.
           Returns: (group, partner_id_to_notify, message)

```

DESCRIPTION -> Use `tuple` instead of `Tuple` for type annotation
LOCATION -> src/services/family_service.py:267:48
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           return group, partner_id, f"Вы успешно присоединились к группе «{group.name}»!"

->     async def leave_group(self, user: User) -> Tuple[bool, Optional[int]]:
           """
           Leaves current family group. Returns (success, partner_id_to_notify).
           """

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/family_service.py:267:60
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           return group, partner_id, f"Вы успешно присоединились к группе «{group.name}»!"

->     async def leave_group(self, user: User) -> Tuple[bool, Optional[int]]:
           """
           Leaves current family group. Returns (success, partner_id_to_notify).
           """

```

DESCRIPTION -> `typing.Tuple` is deprecated, use `tuple` instead
LOCATION -> src/services/parser_service.py:3:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   import re
   from decimal import Decimal, InvalidOperation
-> from typing import Optional, Tuple

   CURRENCY_SUFFIXES = r"(?:руб(?:лей|ля|\.)?|р\b|тг\b|тенге|kzt\b|rub\b|usd\b|\$|€)"


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/parser_service.py:20:34
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       @staticmethod
->     def parse_text(text: str) -> Optional[Tuple[Decimal, str]]:
           """
           Fast regex-based extraction of amount and item name from user message.
           Examples:

```

DESCRIPTION -> Use `tuple` instead of `Tuple` for type annotation
LOCATION -> src/services/parser_service.py:20:43
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

       @staticmethod
->     def parse_text(text: str) -> Optional[Tuple[Decimal, str]]:
           """
           Fast regex-based extraction of amount and item name from user message.
           Examples:

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/services/report_service.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> from datetime import datetime, timedelta, timezone
   from typing import Optional, Dict, Any, List
   from uuid import UUID
   from sqlalchemy import select, func, and_, or_

```

DESCRIPTION -> `typing.Dict` is deprecated, use `dict` instead
LOCATION -> src/services/report_service.py:2:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime, timedelta, timezone
-> from typing import Optional, Dict, Any, List
   from uuid import UUID
   from sqlalchemy import select, func, and_, or_
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/services/report_service.py:2:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime, timedelta, timezone
-> from typing import Optional, Dict, Any, List
   from uuid import UUID
   from sqlalchemy import select, func, and_, or_
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> `typing.List` imported but unused
LOCATION -> src/services/report_service.py:2:41
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime, timedelta, timezone
-> from typing import Optional, Dict, Any, List
   from uuid import UUID
   from sqlalchemy import select, func, and_, or_
   from sqlalchemy.ext.asyncio import AsyncSession

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/report_service.py:17:26
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self,
           user_id: int,
->         family_group_id: Optional[UUID] = None,
           period: str = "month"  # "week", "month", "year"
       ) -> Dict[str, Any]:
           """Generate financial summary and category breakdown for a given period."""

```

DESCRIPTION -> Use `dict` instead of `Dict` for type annotation
LOCATION -> src/services/report_service.py:19:10
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           family_group_id: Optional[UUID] = None,
           period: str = "month"  # "week", "month", "year"
->     ) -> Dict[str, Any]:
           """Generate financial summary and category breakdown for a given period."""
           now = datetime.now(timezone.utc)
           if period == "week":

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/report_service.py:21:28
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       ) -> Dict[str, Any]:
           """Generate financial summary and category breakdown for a given period."""
->         now = datetime.now(timezone.utc)
           if period == "week":
               start_date = now - timedelta(days=7)
           elif period == "year":

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> src/services/transaction_service.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import uuid
   import re
   import asyncio
   import logging

```

DESCRIPTION -> `typing.Tuple` is deprecated, use `tuple` instead
LOCATION -> src/services/transaction_service.py:7:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime, timezone
   from decimal import Decimal
-> from typing import Optional, Tuple, List, Any
   from sqlalchemy import select, func
   from sqlalchemy.ext.asyncio import AsyncSession


```

DESCRIPTION -> `typing.List` is deprecated, use `list` instead
LOCATION -> src/services/transaction_service.py:7:1
RATIONALE -> Rule UP035. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from datetime import datetime, timezone
   from decimal import Decimal
-> from typing import Optional, Tuple, List, Any
   from sqlalchemy import select, func
   from sqlalchemy.ext.asyncio import AsyncSession


```

DESCRIPTION -> `src.models.asset.AssetAccount` imported but unused
LOCATION -> src/services/transaction_service.py:15:30
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from src.models.transaction import Transaction, TransactionSource
   from src.models.alias import UserItemAlias
-> from src.models.asset import AssetAccount, AssetType
   from src.core.exceptions import InvalidTransactionAmountError, TransactionParseError
   from src.services.parser_service import ParserService
   from src.services.category_service import CategoryService

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:33:59
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

   class TransactionService:
->     def __init__(self, session: AsyncSession, ai_service: Optional[AIService] = None):
           self.session = session
           self.ai_service = ai_service or AIService()
           self.category_service = CategoryService(session)

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:39:86
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self.asset_service = AssetService(session)

->     async def _detect_family_partner(self, user: User, text: str, item_name: str) -> Optional[User]:
           """Detect if the transaction is directed to the user's family partner."""
           if not user.family_group_id:
               return None

```

DESCRIPTION -> Use a single `if` statement instead of nested `if` statements
LOCATION -> src/services/transaction_service.py:56:9
RATIONALE -> Rule SIM102. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               return partner

->         if partner.first_name and len(partner.first_name.strip()) >= 2:
               if partner.first_name.strip().lower() in combined_text:
                   return partner


```

DESCRIPTION -> Use a single `if` statement instead of nested `if` statements
LOCATION -> src/services/transaction_service.py:60:9
RATIONALE -> Rule SIM102. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   return partner

->         if partner.username and len(partner.username.strip()) >= 2:
               if partner.username.strip().lower().lstrip("@") in combined_text:
                   return partner


```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:74:17
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       async def _handle_intra_family_mirror(
           self,
->         sender: Optional[User],
           primary_tx: Transaction,
           context_text: Optional[str] = None
       ) -> Optional[User]:

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:76:23
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           sender: Optional[User],
           primary_tx: Transaction,
->         context_text: Optional[str] = None
       ) -> Optional[User]:
           """
           Creates mirror income transaction for family partner if primary transaction is an expense transfer to partner.

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:77:10
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           primary_tx: Transaction,
           context_text: Optional[str] = None
->     ) -> Optional[User]:
           """
           Creates mirror income transaction for family partner if primary transaction is an expense transfer to partner.
           Returns the partner User if mirrored, else None.

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/transaction_service.py:133:16
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               )
               await bot.send_message(partner_id, text)
->         except Exception as exc:
               logger.warning("Failed to send transfer notification to partner %s: %s", partner_id, exc)

       async def _get_alias_category(

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:140:19
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           user_id: int,
           item_name: str,
->         cat_type: Optional[CategoryType] = None
       ) -> Optional[Category]:
           """Local alias lookup (10-15 ms) without sending requests to Gemini."""
           normalized = item_name.strip().lower()

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:141:10
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           item_name: str,
           cat_type: Optional[CategoryType] = None
->     ) -> Optional[Category]:
           """Local alias lookup (10-15 ms) without sending requests to Gemini."""
           normalized = item_name.strip().lower()
           query = select(UserItemAlias).where(

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:192:15
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           self,
           user_id: int,
->         user: Optional[User],
           item: dict,
           cat_type: CategoryType,
           amt: Decimal,

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:196:20
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           cat_type: CategoryType,
           amt: Decimal,
->         asset_amt: Optional[Any],
           context_text: Optional[str] = None
       ) -> Tuple[uuid.UUID, str]:
           raw_curr = item.get("target_currency")

```

DESCRIPTION -> Use `X | None` for type annotations
LOCATION -> src/services/transaction_service.py:197:23
RATIONALE -> Rule UP045. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           amt: Decimal,
           asset_amt: Optional[Any],
->         context_text: Optional[str] = None
       ) -> Tuple[uuid.UUID, str]:
           raw_curr = item.get("target_currency")
           target_currency = (

```

DESCRIPTION -> Use `tuple` instead of `Tuple` for type annotation
LOCATION -> src/services/transaction_service.py:198:10
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           asset_amt: Optional[Any],
           context_text: Optional[str] = None
->     ) -> Tuple[uuid.UUID, str]:
           raw_curr = item.get("target_currency")
           target_currency = (
               raw_curr.strip().upper()

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/transaction_service.py:243:62
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           return asset_acc.id, asset_acc.name

->     async def process_text(self, user_id: int, text: str) -> List[Transaction]:
           """
           Multi-item capable text transaction processing:
           1. Fast Regex parsing (single item)

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/transaction_service.py:253:20
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           parsed = ParserService.parse_text(text)
->         raw_items: List[dict] = []
           discount_percent = None
           discount_amount = None
           total_paid = None

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/transaction_service.py:290:23
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           )

->         transactions: List[Transaction] = []
           notified_partners: List[Tuple[User, float]] = []

           alias_cache = {}

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/transaction_service.py:291:28
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           transactions: List[Transaction] = []
->         notified_partners: List[Tuple[User, float]] = []

           alias_cache = {}
           resolve_cache = {}

```

DESCRIPTION -> Use `tuple` instead of `Tuple` for type annotation
LOCATION -> src/services/transaction_service.py:291:33
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           transactions: List[Transaction] = []
->         notified_partners: List[Tuple[User, float]] = []

           alias_cache = {}
           resolve_cache = {}

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/transaction_service.py:300:20
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               try:
                   amt = Decimal(str(item.get("amount", 0) or 0))
->             except Exception:
                   amt = Decimal("0")

               if amt <= Decimal("0"):

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/transaction_service.py:301:31
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   amt = Decimal(str(item.get("amount", 0) or 0))
               except Exception:
->                 amt = Decimal("0")

               if amt <= Decimal("0"):
                   continue

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/transaction_service.py:303:31
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   amt = Decimal("0")

->             if amt <= Decimal("0"):
                   continue

               raw_name = item.get("item_name") or text

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/transaction_service.py:397:10
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           audio_bytes: bytes,
           mime_type: str = "audio/ogg"
->     ) -> List[Transaction]:
           """Process voice message in-memory without saving .ogg to disk."""
           user = await self.session.get(User, user_id)
           family_group_id = user.family_group_id if user else None

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/transaction_service.py:427:23
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           )

->         transactions: List[Transaction] = []
           notified_partners: List[Tuple[User, float]] = []
           last_raw_text = None


```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/transaction_service.py:428:28
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           transactions: List[Transaction] = []
->         notified_partners: List[Tuple[User, float]] = []
           last_raw_text = None

           for item in raw_items:

```

DESCRIPTION -> Use `tuple` instead of `Tuple` for type annotation
LOCATION -> src/services/transaction_service.py:428:33
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           transactions: List[Transaction] = []
->         notified_partners: List[Tuple[User, float]] = []
           last_raw_text = None

           for item in raw_items:

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/transaction_service.py:434:20
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               try:
                   amt = Decimal(str(item.get("amount", 0) or 0))
->             except Exception:
                   amt = Decimal("0")

               if amt <= Decimal("0"):

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/transaction_service.py:435:31
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   amt = Decimal(str(item.get("amount", 0) or 0))
               except Exception:
->                 amt = Decimal("0")

               if amt <= Decimal("0"):
                   continue

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/transaction_service.py:437:31
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   amt = Decimal("0")

->             if amt <= Decimal("0"):
                   continue

               last_raw_text = item.get("raw_text")

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/transaction_service.py:523:10
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           image_bytes: bytes,
           mime_type: str = "image/jpeg"
->     ) -> List[Transaction]:
           """Process receipt photo in-memory without saving image to disk."""
           user = await self.session.get(User, user_id)
           family_group_id = user.family_group_id if user else None

```

DESCRIPTION -> Use `list` instead of `List` for type annotation
LOCATION -> src/services/transaction_service.py:543:23
RATIONALE -> Rule UP006. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           )

->         transactions: List[Transaction] = []

           alias_cache = {}
           resolve_cache = {}

```

DESCRIPTION -> Do not catch blind exception: `Exception`
LOCATION -> src/services/transaction_service.py:552:20
RATIONALE -> Rule BLE001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               try:
                   amt = Decimal(str(item.get("amount", 0) or 0))
->             except Exception:
                   amt = Decimal("0")

               if amt <= Decimal("0"):

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/transaction_service.py:553:31
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   amt = Decimal(str(item.get("amount", 0) or 0))
               except Exception:
->                 amt = Decimal("0")

               if amt <= Decimal("0"):
                   continue

```

DESCRIPTION -> Verbose expression in `Decimal` constructor
LOCATION -> src/services/transaction_service.py:555:31
RATIONALE -> Rule FURB157. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
                   amt = Decimal("0")

->             if amt <= Decimal("0"):
                   continue

               raw_name = item.get("item_name") or "Чек"

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/transaction_service.py:610:28
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           initial = Decimal(str(user.initial_balance or 0)) if user and user.initial_balance is not None else Decimal(0)

->         now = datetime.now(timezone.utc)
           start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
           if now.month == 12:
               next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/transaction_service.py:611:72
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           now = datetime.now(timezone.utc)
->         start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
           if now.month == 12:
               next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
           else:

```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/transaction_service.py:613:71
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           start_month = datetime(now.year, now.month, 1, 0, 0, 0, tzinfo=timezone.utc)
           if now.month == 12:
->             next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
           else:
               next_month = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)


```

DESCRIPTION -> Use `datetime.UTC` alias
LOCATION -> src/services/transaction_service.py:615:79
RATIONALE -> Rule UP017. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
               next_month = datetime(now.year + 1, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
           else:
->             next_month = datetime(now.year, now.month + 1, 1, 0, 0, 0, tzinfo=timezone.utc)

           MONTH_NAMES_RU = [
               "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",

```

DESCRIPTION -> `datetime.datetime()` called without a `tzinfo` argument
LOCATION -> tests/test_accrual_scheduler.py:14:57
RATIONALE -> Rule DTZ001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       def test_is_last_day_of_month(self):
           # February leap year
->         self.assertTrue(is_last_day_of_month_standalone(datetime(2024, 2, 29)))
           self.assertFalse(is_last_day_of_month_standalone(datetime(2024, 2, 28)))

           # February non-leap year

```

DESCRIPTION -> `datetime.datetime()` called without a `tzinfo` argument
LOCATION -> tests/test_accrual_scheduler.py:15:58
RATIONALE -> Rule DTZ001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           # February leap year
           self.assertTrue(is_last_day_of_month_standalone(datetime(2024, 2, 29)))
->         self.assertFalse(is_last_day_of_month_standalone(datetime(2024, 2, 28)))

           # February non-leap year
           self.assertTrue(is_last_day_of_month_standalone(datetime(2023, 2, 28)))

```

DESCRIPTION -> `datetime.datetime()` called without a `tzinfo` argument
LOCATION -> tests/test_accrual_scheduler.py:18:57
RATIONALE -> Rule DTZ001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           # February non-leap year
->         self.assertTrue(is_last_day_of_month_standalone(datetime(2023, 2, 28)))

           # 30-day month (April)
           self.assertTrue(is_last_day_of_month_standalone(datetime(2024, 4, 30)))

```

DESCRIPTION -> `datetime.datetime()` called without a `tzinfo` argument
LOCATION -> tests/test_accrual_scheduler.py:21:57
RATIONALE -> Rule DTZ001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           # 30-day month (April)
->         self.assertTrue(is_last_day_of_month_standalone(datetime(2024, 4, 30)))
           self.assertFalse(is_last_day_of_month_standalone(datetime(2024, 4, 29)))

           # 31-day month (October)

```

DESCRIPTION -> `datetime.datetime()` called without a `tzinfo` argument
LOCATION -> tests/test_accrual_scheduler.py:22:58
RATIONALE -> Rule DTZ001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           # 30-day month (April)
           self.assertTrue(is_last_day_of_month_standalone(datetime(2024, 4, 30)))
->         self.assertFalse(is_last_day_of_month_standalone(datetime(2024, 4, 29)))

           # 31-day month (October)
           self.assertTrue(is_last_day_of_month_standalone(datetime(2026, 10, 31)))

```

DESCRIPTION -> `datetime.datetime()` called without a `tzinfo` argument
LOCATION -> tests/test_accrual_scheduler.py:25:57
RATIONALE -> Rule DTZ001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python

           # 31-day month (October)
->         self.assertTrue(is_last_day_of_month_standalone(datetime(2026, 10, 31)))
           self.assertFalse(is_last_day_of_month_standalone(datetime(2026, 10, 30)))



```

DESCRIPTION -> `datetime.datetime()` called without a `tzinfo` argument
LOCATION -> tests/test_accrual_scheduler.py:26:58
RATIONALE -> Rule DTZ001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
           # 31-day month (October)
           self.assertTrue(is_last_day_of_month_standalone(datetime(2026, 10, 31)))
->         self.assertFalse(is_last_day_of_month_standalone(datetime(2026, 10, 30)))


   if __name__ == "__main__":

```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> tests/test_discount_service.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import unittest
   from decimal import Decimal
   from src.services.discount_service import DiscountDistributor


```

DESCRIPTION -> Import block is un-sorted or un-formatted
LOCATION -> tests/test_performance_receipt.py:1:1
RATIONALE -> Rule I001. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
-> import pytest
   import asyncio
   import time
   from unittest.mock import AsyncMock, MagicMock

```

DESCRIPTION -> `decimal.Decimal` imported but unused
LOCATION -> tests/test_performance_receipt.py:8:21
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from src.models.user import User
   from src.models.category import Category, CategoryType
-> from decimal import Decimal
   from sqlalchemy.ext.asyncio import AsyncSession
   from sqlalchemy import select


```

DESCRIPTION -> `sqlalchemy.select` imported but unused
LOCATION -> tests/test_performance_receipt.py:10:24
RATIONALE -> Rule F401. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
   from decimal import Decimal
   from sqlalchemy.ext.asyncio import AsyncSession
-> from sqlalchemy import select

   @pytest.mark.asyncio
   async def test_process_receipt_photo_performance():

```

DESCRIPTION -> Do not explicitly `return None` in function if it is the only possible return value
LOCATION -> tests/test_performance_receipt.py:61:9
RATIONALE -> Rule RET501. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       async def mock_find_by_name(*args, **kwargs):
           await asyncio.sleep(0.001)
->         return None

       transaction_service.category_service.get_categories = AsyncMock(side_effect=mock_get_categories)
       transaction_service.category_service.find_by_name = AsyncMock(side_effect=mock_find_by_name)

```

DESCRIPTION -> Useless `return` statement at end of function
LOCATION -> tests/test_performance_receipt.py:61:9
RATIONALE -> Rule PLR1711. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       async def mock_find_by_name(*args, **kwargs):
           await asyncio.sleep(0.001)
->         return None

       transaction_service.category_service.get_categories = AsyncMock(side_effect=mock_get_categories)
       transaction_service.category_service.find_by_name = AsyncMock(side_effect=mock_find_by_name)

```

DESCRIPTION -> Do not explicitly `return None` in function if it is the only possible return value
LOCATION -> tests/test_performance_receipt.py:72:9
RATIONALE -> Rule RET501. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       async def mock_get_alias_category(*args, **kwargs):
           await asyncio.sleep(0.001)
->         return None

       async def mock_resolve_category(*args, **kwargs):
           await asyncio.sleep(0.001)

```

DESCRIPTION -> Useless `return` statement at end of function
LOCATION -> tests/test_performance_receipt.py:72:9
RATIONALE -> Rule PLR1711. Fixing this improves code quality, readability, and prevents potential runtime errors.
CODE CONTEXT ->
```python
       async def mock_get_alias_category(*args, **kwargs):
           await asyncio.sleep(0.001)
->         return None

       async def mock_resolve_category(*args, **kwargs):
           await asyncio.sleep(0.001)

```
