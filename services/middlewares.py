from starlette.requests import Request


async def check_auth(request: Request, call_next):
    # TODO: Проверка токена в хедерах
    # fail2ban?
    return ...
