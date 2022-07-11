import hashlib
from functools import wraps

from services.tokens import get_txt_quiz_user_id_token, get_admin_user_id_token


async def check_auth(mode):
    if mode == "txt_quiz":

        async def inner_dec(query):
            @wraps(query)
            async def _check_auth(*args, **kwargs):
                uid, hash_token = get_txt_quiz_user_id_token()
                if uid is None or hash_token is None:
                    return "Unauthorized client error ", 401
                # res = database.login(uid, hash_token)
                # if not res:
                #     return "Unauthorized client error ", 401
                return await query(*args, **kwargs)

            return _check_auth

    elif mode == "admin":

        async def inner_dec(query):
            @wraps(query)
            async def _check_auth(*args, **kwargs):
                _, login, password = get_admin_user_id_token()
                if login is None or password is None:
                    return "Unauthorized client error ", 401
                # res = database.admin_login(
                #     login, hashlib.sha256(str(password).encode()).hexdigest()
                # )
                # if res is None:
                #     return "Unauthorized client error ", 401
                return await query(*args, **kwargs)

            return _check_auth

    else:
        raise "Unknown auth"
    return inner_dec
