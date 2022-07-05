from fastapi import APIRouter

from services.tokens import create_token

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.get("/token")
def get_token():
    """
    Создает и возвращает токен юзера
    :return:
    """
    """{"x-api-key": x_api_key}"""
    return create_token()
