import secrets

from utils.database import async_cursor


@async_cursor(do_commit=True, return_conn=True)
async def create_token(cursor, conn):
    hash_token = secrets.token_hex(32)
    state = {}
    await cursor.execute("""
        INSERT INTO Passage (hash_token, state) VALUES (%s, %s,) RETURNING if;
    """, (hash_token, state, ))
    await conn.commit()
    user_id = await cursor.fetchone()
    return user_id[0] if user_id else None

