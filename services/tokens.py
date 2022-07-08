import binascii
import datetime
import logging
import os
import secrets
import xxtea
from urllib import request

from utils.database import async_cursor

DATETIME_FORMAT = "%Y-%m-%d_%H-%M-%S"

logger = logging.getLogger(__name__)


def decoder_data(data, key):
    try:
        enc_data_byte_hex = data.encode("utf-8")  # bytes of encoded data
        # byted hex of encoded data
        enc_data = binascii.unhexlify(enc_data_byte_hex)
        dec_data = xxtea.decrypt_utf8(enc_data, key)  # bytes of decoded data
    except Exception:
        dec_data = ""
    return dec_data


def get_admin_user_id_token():
    try:
        token = request.headers.get("x-api-key")
        data = decoder_data(
            token, os.environ.get("X_API_KEY_ADMIN_USER_XXTEA_TOKEN")
        ).split(":")
        if len(data) == 3:
            timestamp, login, password = data
            if (
                datetime.datetime.now() - datetime.datetime.strptime(timestamp, DATETIME_FORMAT)
            ).total_seconds() < float(os.environ.get("PERMANENT_SESSION_LIFETIME")):
                return timestamp, login, password
        else:
            logger.info("Can't decode api key")
    except Exception as ex:
        logger.error(f"Error in {ex}")

    return None, None, None


def get_txt_quiz_user_id_token():
    token = request.headers.get("x-api-key")

    data = decoder_data(token, os.environ.get("X_API_KEY_QUIZ_USER_XXTEA_TOKEN")).split(":")
    if len(data) == 2:
        uid, hash_token = data
    else:
        uid, hash_token = None, None
    return uid, hash_token


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

