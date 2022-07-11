import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from utils.env import load_env_variables

from views.admin_controller import router as admin_router
from views.auth_controller import router as auth_router
from views.quiz_controller import router as quiz_router
from views.static_controller import router as static_router


load_env_variables(f"app.{os.environ.get('ENV', 'dev')}.yaml")  # ENV: dev/production в зависимости от окружения берет конфиг файл

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

origins = [  # TEMP
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(quiz_router)
app.include_router(static_router)
# drafts = Drafts(database)
