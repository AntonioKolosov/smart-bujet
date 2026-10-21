import asyncio
import logging
from sqlalchemy import text
from src.core.database import engine
from src.core.security import encrypt_value, blind_index

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_argon_encryption")

CASCADE_PLPGSQL = """
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN (
        SELECT tc.table_name, tc.constraint_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND ccu.table_name = 'users'
          AND ccu.column_name = 'id'
          AND kcu.column_name = 'user_id'
    ) LOOP
        EXECUTE 'ALTER TABLE ' || quote_ident(r.table_name) || ' DROP CONSTRAINT ' || quote_ident(r.constraint_name);
        EXECUTE 'ALTER TABLE ' || quote_ident(r.table_name) || ' ADD CONSTRAINT ' || quote_ident(r.constraint_name) || ' FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE';
    END LOOP;
END $$;
"""


async def run_migration():
    if engine is None:
        logger.error("Database engine not configured.")
        return

    logger.info("Starting Argon Security Migration...")

    async with engine.begin() as conn:
        logger.info("1. Upgrading column lengths and schema...")
        await conn.execute(text("ALTER TABLE transactions ALTER COLUMN item_name TYPE VARCHAR(512);"))
        await conn.execute(text("ALTER TABLE asset_accounts ALTER COLUMN name TYPE VARCHAR(512);"))
        await conn.execute(text("ALTER TABLE credit_accounts ALTER COLUMN name TYPE VARCHAR(512);"))
        await conn.execute(text("ALTER TABLE credit_accounts ALTER COLUMN bank_name TYPE VARCHAR(512);"))
        await conn.execute(text("ALTER TABLE users ALTER COLUMN first_name TYPE VARCHAR(512);"))
        await conn.execute(text("ALTER TABLE user_item_aliases ALTER COLUMN item_name_normalized TYPE VARCHAR(64);"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS has_accepted_terms BOOLEAN DEFAULT FALSE;"))

        # Check if table user_agent_memories exists
        res = await conn.execute(text("SELECT to_regclass('user_agent_memories');"))
        if res.scalar():
            await conn.execute(text("ALTER TABLE user_agent_memories ALTER COLUMN fact_text TYPE TEXT;"))

        logger.info("2. Applying ON DELETE CASCADE to foreign keys pointing to users.id...")
        await conn.execute(text(CASCADE_PLPGSQL))

        logger.info("3. Migrating users (username=NULL, has_accepted_terms=TRUE, encrypt first_name)...")
        users = (await conn.execute(text("SELECT id, first_name FROM users;"))).fetchall()
        for u_id, fn in users:
            new_fn = encrypt_value(fn) if fn and not fn.startswith("enc:v1:") else fn
            await conn.execute(
                text("UPDATE users SET username = NULL, has_accepted_terms = TRUE, first_name = :fn WHERE id = :id"),
                {"fn": new_fn, "id": u_id}
            )

        logger.info("4. Migrating transactions (encrypt item_name, clear raw_text)...")
        txs = (await conn.execute(text("SELECT id, item_name FROM transactions WHERE item_name NOT LIKE 'enc:v1:%';"))).fetchall()
        for tx_id, item_name in txs:
            enc_name = encrypt_value(item_name)
            await conn.execute(
                text("UPDATE transactions SET item_name = :enc_name, raw_text = NULL WHERE id = :id"),
                {"enc_name": enc_name, "id": tx_id}
            )
        await conn.execute(text("UPDATE transactions SET raw_text = NULL WHERE raw_text IS NOT NULL;"))

        logger.info("5. Migrating asset_accounts (encrypt name)...")
        assets = (await conn.execute(text("SELECT id, name FROM asset_accounts WHERE name NOT LIKE 'enc:v1:%';"))).fetchall()
        for a_id, name in assets:
            enc_name = encrypt_value(name)
            await conn.execute(
                text("UPDATE asset_accounts SET name = :enc_name WHERE id = :id"),
                {"enc_name": enc_name, "id": a_id}
            )

        logger.info("6. Migrating credit_accounts (encrypt name, bank_name)...")
        credits = (await conn.execute(text("SELECT id, name, bank_name FROM credit_accounts;"))).fetchall()
        for c_id, name, bank_name in credits:
            enc_name = encrypt_value(name) if name and not name.startswith("enc:v1:") else name
            enc_bank = encrypt_value(bank_name) if bank_name and not bank_name.startswith("enc:v1:") else bank_name
            await conn.execute(
                text("UPDATE credit_accounts SET name = :name, bank_name = :bank WHERE id = :id"),
                {"name": enc_name, "bank": enc_bank, "id": c_id}
            )

        logger.info("7. Migrating user_item_aliases (hash item_name_normalized with blind_index)...")
        aliases = (await conn.execute(text("SELECT id, item_name_normalized FROM user_item_aliases WHERE length(item_name_normalized) != 64;"))).fetchall()
        for al_id, alias_name in aliases:
            hashed_alias = blind_index(alias_name)
            await conn.execute(
                text("UPDATE user_item_aliases SET item_name_normalized = :hash WHERE id = :id"),
                {"hash": hashed_alias, "id": al_id}
            )

        # Neutralize family names
        logger.info("8. Neutralizing family names...")
        await conn.execute(text("UPDATE family_groups SET name = 'Семейный бюджет' WHERE name LIKE 'Семья %';"))

        # Clear classification feedback original_text if exists
        res = await conn.execute(text("SELECT to_regclass('user_classification_feedback');"))
        if res.scalar():
            await conn.execute(text("UPDATE user_classification_feedback SET original_text = NULL WHERE original_text IS NOT NULL;"))

        # Memory facts if table exists
        res = await conn.execute(text("SELECT to_regclass('user_agent_memories');"))
        if res.scalar():
            logger.info("Migrating user_agent_memories (encrypt fact_text)...")
            memories = (await conn.execute(text("SELECT id, fact_text FROM user_agent_memories WHERE fact_text NOT LIKE 'enc:v1:%';"))).fetchall()
            for m_id, fact_text in memories:
                enc_fact = encrypt_value(fact_text)
                await conn.execute(
                    text("UPDATE user_agent_memories SET fact_text = :enc WHERE id = :id"),
                    {"enc": enc_fact, "id": m_id}
                )

    await engine.dispose()
    logger.info("✅ Migration completed successfully!")


if __name__ == "__main__":
    asyncio.run(run_migration())
