import functools

import aiopg
import os


async def _async_db_connect():
    return aiopg.sa.create_engine(user=os.environ.get("DB_USER"),
                                  database=os.environ.get("DB_DATABASE"),
                                  host=os.environ.get("DB_HOST"),
                                  password=os.environ.get("DB_PASSWORD"),
                                  max_size=os.environ.get("DB_MAX_SIZE"))


def async_cursor(do_commit=False, return_conn=False):
    def method_wrap(method):
        @functools.wraps(method)
        async def wrap(*args, **kwargs):
            pool = await _async_db_connect()
            try:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        if return_conn:
                            result = await method(cursor, return_conn, *args, **kwargs)
                        else:
                            result = await method(cursor, *args, **kwargs)
                    if do_commit:
                        await conn.commit()
                return result
            finally:
                await cursor.close()
        return wrap
    return method_wrap
