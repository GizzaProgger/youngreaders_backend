import copy
import json
import logging
import re
import string
import time
import traceback
from datetime import datetime

import yaml
from sqlalchemy.dialects.postgresql import ext

from services.legacy_db_wrapper import get_quote_id, SetEncoder
from utils import database

logger = logging.getLogger(__name__)

yaml.warnings({"YAMLLoadWarning": False})

ACTIVE_DRAFT_NAME = "(active_draft)"


def valid_hex(id_string: str) -> bool:
    return all(c in string.hexdigits for c in id_string)


def validate_quote_id(quote_id_string: str) -> (bool, str):
    if not valid_hex(quote_id_string):
        return False, f"Quote id '{quote_id_string}' is not valid HEX."

    _, text, draft_name = database.get_active_draft()
    quotes = drafts.extract_quotes(text)
    if quote_id_string not in [q['id'] for q in quotes]:
        logger.info([q['id'] for q in quotes])
        return False, f"Quote with id '{quote_id_string}' does not exist."
    return True, 'OK'


def validate_comment_body(text: str) -> (bool, str):
    if len(text) == 0:
        return False, "Field can not be blank"
    return True, "OK"


def validate_limit(limit: str) -> (bool, int):
    try:
        limit = int(limit)
        return limit >= 0, limit
    except ValueError:
        return False, -1


def validate_offset(offset: str) -> (bool, int):
    try:
        offset = int(offset)
        return offset > 0, offset
    except ValueError:
        return False, -1


def is_mail_valid(email) -> bool:
    """Функция проверки почты"""
    mail_regex = re.compile(r'([A-Za-z0-9]+[.-_])*[A-Za-z0-9]+@[A-Za-z0-9-]+(\.[A-Z|a-z]{2,})+')
    return bool(re.fullmatch(mail_regex, email))


class DB:
    def __init__(self):
        self.active_draft_name = ACTIVE_DRAFT_NAME
        self.connect = None
        self.host = None
        self.port = None
        self.dbname = None
        self.user = None
        self.password = None
        self.schema = None
        self.last_error_message = None

    def db_connect(
        self,
        host=None,
        port=None,
        dbname=None,
        user=None,
        password=None,
        schema=None,
        *args,
        **kwargs
    ):
        self.host = host
        self.port = port
        self.dbname = dbname
        self.user = user
        self.password = password
        self.schema = schema
        self._db_connect()

    def _db_connect(self):
        logger.info(
            {
                "host": self.host,
                "port": self.port,
                "dbname": self.dbname,
                "user": self.user,
                "password": self.password,
                "options": "-c search_path={}".format(self.schema)
                if self.schema
                else None,
            }
        )
        try:
            self.connect = pg.connect(
                host=self.host,
                port=self.port,
                dbname=self.dbname,
                user=self.user,
                password=self.password,
                options="-c search_path={}".format(self.schema)
                if self.schema
                else None,
            )
        except Exception:
            self.last_error_message = traceback.format_exc()
            logger.error(traceback.format_exc())
            self.connect = None

    def healthcheck(self):
        if self.last_error_message:
            return (
                False,
                "A database error occurred, last message :\n {}".format(
                    self.last_error_message
                ),
            )
        self.check_db_availability()
        if self.last_error_message:
            return (
                False,
                "A database error occurred, last message :\n {}".format(
                    self.last_error_message
                ),
            )
        return True, "Database availability"
        # return False, "Database availability"

    def recovery(self):
        if self.connect:
            transaction_status = self.connect.get_transaction_status()
            if transaction_status == ext.TRANSACTION_STATUS_INERROR:
                logger.warning("The session is idle in a failed transaction block")
                self.last_error_message = None
                self.connect.rollback()

            if transaction_status == ext.TRANSACTION_STATUS_UNKNOWN:
                logger.error("The connection with the server is bad.")
                self._db_connect()
        else:
            self._db_connect()

    def check_db_availability(self):
        def easy_query():
            try:
                with self.connect.cursor() as curs:
                    curs.execute("SELECT 1;")
                return True
            except Exception:
                self.last_error_message = traceback.format_exc()
                logger.error(traceback.format_exc())

        # check connection
        if not (self.connect and easy_query()):
            self.recovery()
            return self.connect and easy_query()
        return True

    def connection_decorator(by_exc_return=None):
        def inner_dec(query):
            def keep_connection(self, *args, **kwargs):
                try:
                    assert bool(self.connect), db_configs[
                        "DB_ERROR_AVAILABLE_CONNECTION_MSG"
                    ]
                    results = query(self, *args, **kwargs)
                except Exception:
                    self.last_error_message = traceback.format_exc()
                    logger.warning(traceback.format_exc())
                    self.recovery()
                    logger.info("Restart procedure starts")
                    results = by_exc_return
                    if not self.check_db_availability():
                        logger.info("Restart procedure is failed")
                    else:
                        logger.info("Restart procedure is finished")

                return results

            return keep_connection

        return inner_dec

    @connection_decorator(None)
    def create_passage(self, hash_token, state):
        assert isinstance(hash_token, str)
        assert isinstance(state, dict)
        with self.connect.cursor() as curs:
            curs.execute(
                "insert into passage (hash_token,state) values(%s,%s) returning id;",
                (hash_token, json.dumps(state, cls=SetEncoder)),
            )
            self.connect.commit()
            response = curs.fetchone()
            id = response[0] if response else None
        return id

    @connection_decorator(None)
    def login(self, id, hash_token):
        assert isinstance(hash_token, str)
        with self.connect.cursor() as curs:
            curs.execute(
                "select 1 from passage where id=%s and hash_token=%s;", (id, hash_token)
            )
            response = curs.fetchone()
            res = response[0] if response else None
        return res

    @connection_decorator(None)
    def get_state(self, id):
        with self.connect.cursor() as curs:
            curs.execute("select state from passage where id=%s;", (id,))
            response = curs.fetchone()
            state = response[0] if response else None
        return state

    @connection_decorator(None)
    def udp_state(self, id, state):
        with self.connect.cursor() as curs:
            curs.execute(
                "update passage set state = %s where id=%s;",
                (json.dumps(state, cls=SetEncoder), id),
            )
            self.connect.commit()

    @connection_decorator([])
    def get_steps_data(self, id):
        with self.connect.cursor() as curs:
            curs.execute(
                "select key, draft_name, full_data, summary_data, timestamp from step_data where passage_id=%s;",
                (id,),
            )
            steps_data_tab = curs.fetchall()
            steps_data = []
            for (key, draft_name, full_data, summary_data, timestamp) in steps_data_tab:
                steps_data.append(
                    {
                        "key": key,
                        "draft_name": draft_name,
                        "full_data": full_data,
                        "summary_data": summary_data,
                        "timestamp": timestamp,
                    }
                )
            return steps_data

    @connection_decorator(None)
    def add_step(self, id, key, full_data, summary_data, draft_name, stats):
        assert isinstance(draft_name, str)
        with self.connect.cursor() as curs:
            full_data = json.dumps(full_data, cls=SetEncoder)
            summary_data = json.dumps(summary_data, cls=SetEncoder)
            stats = json.dumps(stats, cls=SetEncoder)
            curs.execute(
                "insert into step_data (passage_id, key, full_data, summary_data, draft_name, stats) \
                values(%s,%s,%s,%s,%s,%s) returning id;",
                (id, key, full_data, summary_data, draft_name, stats),
            )
            self.connect.commit()
            response = curs.fetchone()
            res = str(response[0]) if response else None
        return res

    @connection_decorator(None)
    def add_tracking(self, step_data_id, full_data, summary_data):
        with self.connect.cursor() as curs:
            full_data = (
                full_data
                if isinstance(full_data, list)
                or isinstance(full_data, dict)
                or isinstance(full_data, set)
                else [full_data]
            )
            summary_data = (
                summary_data
                if isinstance(summary_data, list)
                or isinstance(summary_data, dict)
                or isinstance(summary_data, set)
                else [summary_data]
            )
            full_data = json.dumps(full_data, cls=SetEncoder)
            summary_data = json.dumps(summary_data, cls=SetEncoder)
            curs.execute(
                "insert into tracking_data (step_data_id, full_data, summary_data) \
                values(%s,%s,%s) returning 1;",
                (step_data_id, full_data, summary_data),
            )
            self.connect.commit()
            response = curs.fetchone()
            res = str(response[0]) if response else None
        return res

    @connection_decorator(None)
    def admin_login(self, login, password):
        with self.connect.cursor() as curs:
            curs.execute(
                "select id from admin where login=%s and password=%s;",
                (login, password),
            )
            response = curs.fetchone()
            admin_id = str(response[0]) if response else None
        return admin_id

    @connection_decorator([])
    def get_draft_names(self):
        with self.connect.cursor() as curs:
            curs.execute("select distinct draft_name from draft_version;")
            self.connect.commit()
            response = curs.fetchall()
            res = [draft_name[0] for draft_name in response]
        if self.get_active_draft()[0]:
            res += [self.active_draft_name]
        return res

    @connection_decorator()
    def add_draft(self, text, draft_name, publisher, purchase_link, admin_id):
        assert draft_name != self.active_draft_name
        with self.connect.cursor() as curs:
            curs.execute(
                "insert into draft_version(text, draft_name, publisher, purchase_link, admin_id) \
                            values(%s, %s, %s, %s, %s) returning id;",
                (text, draft_name, publisher, purchase_link, admin_id),
            )
            self.connect.commit()
            response = curs.fetchone()
            res = str(response[0]) if response else None
        return res

    @connection_decorator()
    def set_active_draft(self, draft_id):
        with self.connect.cursor() as curs:
            curs.execute(
                "update draft_version set active = true where id=%s;", (draft_id,)
            )
            curs.execute(
                "update draft_version set active = false where id!=%s and active = true;",
                (draft_id,),
            )
            self.connect.commit()

    @connection_decorator([None, None, None])
    def get_active_draft(self):
        with self.connect.cursor() as curs:
            curs.execute(
                "select id, text, draft_name, publisher, purchase_link from draft_version where active = true order by timestamp desc limit 1;"
            )
            self.connect.commit()
            response = curs.fetchone()
            id, text, draft_name, publisher, purchase_link = (
                (str(response[0]), str(response[1]), str(response[2]), str(response[3]), str(response[4]))
                if response
                else (None, None, None, None, None)
            )
        return id, text, draft_name

    @connection_decorator([None, None, None])
    def get_active_draft_version(self):
        with self.connect.cursor() as curs:
            active_draft = None
            non_selected_draft = None

            # 1
            curs.execute(
                "select id from daily_drafts where active = true limit 1;"
            )
            self.connect.commit()
            active_draft = curs.fetchone()[0]

            # 2
            curs.execute(
                "select * from draft_version where id != (select draft_id from daily_drafts where active=True);"
            )
            self.connect.commit()
            non_selected_drafts = curs.fetchall()
            print("NON_SELECTED_DRAFTS:\t", non_selected_drafts, flush=True)
            random_number = random.randint(0, len(non_selected_drafts)-1)
            non_selected_draft = non_selected_drafts[random_number]

            # 3
            curs.execute(
                "insert into daily_drafts (draft_id, active, was_selected, date) values({draft_id}, TRUE, TRUE, '{date}')".format(date=datetime.now().strftime("%Y-%m-%d"),
                                                                                                                                  draft_id=non_selected_draft[0])
            )
            self.connect.commit()

            # 4
            curs.execute(
                "update daily_drafts set active=FALSE where id={active_draft_id}".format(
                    active_draft_id=active_draft)
            )
            self.connect.commit()
            id, text, draft_name, publisher, purchase_link = (
                (str(non_selected_draft[0]), str(non_selected_draft[1]), str(non_selected_draft[2]), str(non_selected_draft[3]), str(non_selected_draft[4]))
                if non_selected_draft
                else (None, None, None, None, None)
            )
        return id, text, draft_name

    @connection_decorator([None, None, None])
    def get_draft_by_name(self, draft_name):
        if draft_name == self.active_draft_name:
            id, text, draft_name = self.get_active_draft()
        else:
            with self.connect.cursor() as curs:
                curs.execute(
                    "select id, text, draft_name from draft_version where draft_name=%s order by timestamp desc limit 1;",
                    (draft_name,),
                )
                self.connect.commit()
                response = curs.fetchone()
                id, text, draft_name, publisher, purchase_link = (
                    (str(response[0]), str(response[1]), str(response[2]), str(response[3]), str(response[4]))
                    if response
                    else (None, None, None, None, None)
                )
        return id, text, draft_name

    @connection_decorator([None, None, None])
    def get_draft_by_id(self, draft_id):
        with self.connect.cursor() as curs:
            curs.execute(
                "select id, text, draft_name, publisher, purchase_link from draft_version where id=%s order by timestamp desc limit 1;",
                (draft_id,),
            )
            self.connect.commit()
            response = curs.fetchone()
            id, text, draft_name, publisher, purchase_link = (
                (str(response[0]), str(response[1]), str(response[2]), str(response[3]), str(response[4]))
                if response
                else (None, None, None, None, None)
            )
        return id, text, draft_name

    @connection_decorator()
    def add_feedback(self, passage_id: int, email: str, name: str, main_text: str):
        """Добавить отзыв"""
        assert isinstance(passage_id, int)
        assert isinstance(email, str)
        assert isinstance(name, str)
        assert isinstance(main_text, str)

        with self.connect.cursor() as curs:
            try:
                curs.execute(
                "insert into feedbacks (passage_id, email, user_name, main_text) \
                values(%s,%s,%s,%s);",
                (passage_id, email, name, main_text),
            )
            except:
                return False, "Отзыв от этого пользователя уже получен"
            self.connect.commit()
            return True, "Отзыв успешно добавлен"

    @connection_decorator()
    def add_quote(self, qid):
        # add "quote-likes" object, not likes to quote!
        with self.connect.cursor() as curs:
            curs.execute(
                "INSERT INTO quote_likes (quote_id, likes) VALUES (%s, 0) ON CONFLICT DO NOTHING;",
                (qid,))
            self.connect.commit()
            state = curs.rowcount
        return state

    @connection_decorator()
    def increment_quote_likes(self, qid):
        with self.connect.cursor() as curs:
            curs.execute(
                "UPDATE quote_likes SET likes=likes+1 WHERE quote_id=%s RETURNING likes;", (qid,))
            self.connect.commit()
            response = curs.fetchone()
            state = response[0] if response else None
        return state

    @connection_decorator()
    def get_quote_likes(self, qid) -> bool:
        with self.connect.cursor() as curs:
            curs.execute("SELECT likes FROM quote_likes WHERE quote_id=%s;", (qid,))
            response = curs.fetchone()
            state = response[0] if response else None
        return state

    @connection_decorator()
    def get_quote_likes_count_filtered(self, ids: list, timestamp_from: datetime, timestamp_to: datetime) -> list:
        with self.connect.cursor() as curs:
            curs.execute("SELECT COUNT(quote_id), quote_id FROM user_likes "
                         "WHERE quote_id IN %s "
                         "AND timestamp >= %s AND timestamp <= %s "
                         "GROUP BY quote_id "
                         "ORDER BY COUNT(quote_id) DESC;", (tuple(ids), timestamp_from.strftime('%Y-%m-%d %H:%M:%S'), timestamp_to.strftime('%Y-%m-%d %H:%M:%S')))
            response = curs.fetchall()
            results = []
            for (count_liked, qid) in response:
                results.append({
                    "count": count_liked,
                    "id": qid
                })
        return results

    @connection_decorator()
    def is_already_commented(self, uid, qid):
        with self.connect.cursor() as curs:
            curs.execute("SELECT id FROM quote_comments WHERE (passage_id, quote_id)=(%s, %s);", (uid, qid))
            response = curs.fetchone()
            state = True if response else False
        return state

    @connection_decorator()
    def get_latest_comments(self, quote_id: str, limit: int = 10) -> list:
        with self.connect.cursor() as curs:
            curs.execute("SELECT id, passage_id, quote_id, content, timestamp FROM quote_comments "
                         "WHERE quote_id = %s "
                         "ORDER BY timestamp DESC LIMIT %s;", (quote_id, str(limit),))
            response = curs.fetchall()
            results = []
            for (cid, passage_id, quote_id, content, timestamp) in response:
                results.append({
                    "id": cid,
                    "passage_id": passage_id,
                    "quote_id": quote_id,
                    "content": content,
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S")
                })
        return results

    @connection_decorator()
    def get_all_comments(self, timestamp_from: datetime, timestamp_to: datetime):
        with self.connect.cursor() as curs:
            curs.execute("SELECT id, passage_id, quote_id, content, timestamp FROM quote_comments "
                         "WHERE timestamp >= %s AND timestamp <= %s "
                         "ORDER BY timestamp DESC;", (timestamp_from.strftime('%Y-%m-%d %H:%M:%S'), timestamp_to.strftime('%Y-%m-%d %H:%M:%S')))
            response = curs.fetchall()
            results = []
            for (cid, passage_id, quote_id, content, timestamp) in response:
                results.append({
                    "id": cid,
                    "passage_id": passage_id,
                    "quote_id": quote_id,
                    "content": content,
                    "timestamp": timestamp
                })
        return results

    @connection_decorator()
    def get_quote_comments(self, qid, limit, offset):
        with self.connect.cursor() as curs:
            curs.execute("SELECT id, content, quote_id "
                         "FROM quote_comments "
                         "WHERE quote_id=%s "
                         "LIMIT %s OFFSET %s;", (qid, limit, offset))
            response = curs.fetchall()
            results = []
            for (cid, content, quote_id) in response:
                results.append({
                    "id": cid,
                    "content": content,
                    "quote_id": quote_id
                })
        return results

    @connection_decorator()
    def add_comment(self, uid, qid, content) -> (bool, str):
        with self.connect.cursor() as curs:
            curs.execute(
                "INSERT INTO quote_comments (passage_id, quote_id, content) VALUES (%s, %s, %s);",
                (uid, qid, content))
            self.connect.commit()
            state = curs.rowcount
            logger.debug(state)
        return state == 1, "OK"

    @connection_decorator(False)
    def is_already_liked(self, uid, qid):
        with self.connect.cursor() as curs:
            curs.execute("SELECT 1 FROM user_likes WHERE (passage_id, quote_id)=(%s, %s);", (uid, qid))
            response = curs.fetchone()
            state = True if response else False
        return state

    @connection_decorator(False)
    def add_user_like(self, uid, qid):
        with self.connect.cursor() as curs:
            curs.execute(
                "INSERT INTO user_likes (passage_id, quote_id) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                (uid, qid))
            self.connect.commit()
            state = curs.rowcount
        return state


class Drafts:
    def __init__(self, database):
        self.database = database
        self.change_draft(wait=True)

    @staticmethod
    def extract_quotes(yaml_text: str) -> list:
        data = yaml.safe_load(yaml_text)
        quotes = []
        for result_id, result in data['results'].items():
            for book in result['books']:
                for quote in book['quotes']:
                    quotes.append({
                        'id': get_quote_id(quote),
                        'text': quote,
                        'book_name': book['name'],
                        'book_author': book['author'],
                        'result_id': result_id
                    })
        return quotes

    @staticmethod
    def extract_values(obj, key_name, values_container, key_exceptions):
        if isinstance(obj, list):
            [
                Drafts.extract_values(i, key_name, values_container, key_exceptions)
                for i in obj
            ]
        elif isinstance(obj, dict):
            for k in obj.keys():
                if k in key_exceptions:
                    continue
                elif k != key_name:
                    Drafts.extract_values(
                        obj[k], key_name, values_container, key_exceptions
                    )
                else:
                    hash_key = hashlib.sha256(json.dumps(obj[k]).encode()).hexdigest()
                    values_container[hash_key] = obj[k]
                    obj[k] = str(hash_key)

    def change_draft(self, draft_name=None, text=None, wait=False):
        while True:
            try:
                if text is None or draft_name is None:
                    _, text, draft_name = self.database.get_draft_by_name(
                        ACTIVE_DRAFT_NAME
                    )
                self.current_draft = yaml.safe_load(text)
                self.current_draft_name = draft_name
                self.values_container = {}
                Drafts.extract_values(
                    self.current_draft, "value", self.values_container, ["gui_options"]
                )
                quote_ids = set()
                for result in self.current_draft.get("results", {}).values():
                    for book in result.get("books", []):
                        for quote in book.get("quotes", []):
                            quote_ids.add(get_quote_id(quote))
                for qid in quote_ids:
                    self.database.add_quote(qid)
                return True
            except Exception as ex:
                logger.error(ex)
                if not wait:
                    return False
                else:
                    time.sleep(2)

    def get_draft_names(self):
        return self.database.get_draft_names()

    def get_draft(self):
        return copy.deepcopy(self.current_draft)

    def get_values(self):
        return self.values_container
