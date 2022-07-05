import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils.env import load_env_variables

load_env_variables(os.environ.get("ENV"))  # ENV: dev/production в зависимости от окружения берет конфиг файл

app = FastAPI()

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
