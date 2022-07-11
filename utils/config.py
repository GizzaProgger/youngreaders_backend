import os

db_configs = dict()

db_configs["RECONNECT_ATTEMPT_NUMBER"] = os.getenv("RECONNECT_ATTEMPT_NUMBER", 3)
db_configs["DB_HOST"] = os.getenv("DB_HOST", "localhost")
db_configs["DB_PORT"] = os.getenv("DB_PORT", "5432")
db_configs["DB_DBNAME"] = os.getenv("DB_DBNAME", "young_readers_drafted_txt_quiz_db")
db_configs["DB_USER"] = os.getenv("DB_USER", "young_readers_drafted_txt_quiz_db_user")
db_configs["DB_PASSWORD"] = os.getenv("DB_PASSWORD", "win_must_die")
db_configs["DB_MAX_POOL_SIZE"] = os.getenv("DB_MAX_POOL_SIZE", 1000)
db_configs["DB_SCHEMA"] = os.getenv("DB_SCHEMA")

db_configs["DB_MEMBER_LOGIN_LEN"] = 7
db_configs["DB_MAX_LEN_OF_NAME"] = 127
db_configs["DB_MAX_LEN_OF_DESC"] = 511
db_configs["DB_AVAILABLE_QUIZ_DATA_TYPES"] = ["login", "text_quiz", "img_quiz", "eval"]
db_configs["DB_ERROR_AVAILABLE_CONNECTION_MSG"] = "Database connection is not available"
