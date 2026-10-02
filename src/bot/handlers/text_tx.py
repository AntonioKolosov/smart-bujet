from aiogram import Router, F
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from src.services.transaction_service import TransactionService

router = Router()

@router.message(F.text & ~F.text.startswith('/'))
async def process_text_transaction(message: Message, session: AsyncSession):
    tx_service = TransactionService(session)
    tx = await tx_service.process_text(user_id=message.from_user.id, text=message.text)
    
    type_label = "Расход" if tx.type == "expense" else "Доход"
    category_name = tx.category.name if tx.category else "Общее"
    
    await message.reply(
        f"✅ <b>{type_label} записан!</b>\n"
        f"📌 Позиция: <b>{tx.item_name}</b>\n"
        f"💰 Сумма: <b>{tx.amount:,.2f}</b>\n"
        f"📁 Категория: <b>{category_name}</b>"
    )

