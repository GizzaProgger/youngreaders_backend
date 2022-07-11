import copy
import logging

from fastapi import APIRouter

from models.comments import Comment
from models.feedback import Feedback
from models.like_post import LikePostBody
from models.result_post import Result
from models.step_post import StepPostBody
from services.legacy_db_wrapper import Drafts
from services.middlewares import check_auth
from services.quize import validate_quote_id, validate_comment_body, validate_limit, is_mail_valid
from services.tokens import get_txt_quiz_user_id_token, decode_result, get_quote_id

router = APIRouter(prefix="/quiz", tags=["Quiz"])
logger = logging.getLogger(__name__)


@router.post("/result", tags=["Quiz"])
# @check_auth('txt_quiz')
async def results_handler(request: Result):
    uid, _ = get_txt_quiz_user_id_token()
    encoded_result = request.json["result"]
    result = decode_result(encoded_result)
    if result == {}:
        logger.debug(f"Can't decode bad result request: encoded_result={encoded_result}")
    else:
        logger.debug(f"Requested result: result={result}")
    draft = Drafts.get_draft()
    steps = draft.get("steps", {})
    available_results = draft.get("results", {})
    step = steps.get(result.get("step"), {"title": "Результаты теста", "type": "bad result"})
    if "handlers" in step:
        del step["handlers"]
    if "next_steps" in step:
        del step["next_steps"]
    if "stats" in step:
        del step["stats"]
    if "body_hidden_keys" in step:
        for k in step["body_hidden_keys"]:
            del step["body_hidden_keys"][k]
    logger.debug(f"step = {step}")
    logger.debug(f"result = {result}")
    step = copy.deepcopy(step)
    results = list(set(result.get("results")))

    def manage_quotes(res):
        res = copy.deepcopy(res)
        try:
            if res:
                for book in res.get("books", []):
                    quotes = []
                    for quote_text in book.get("quotes", []):
                        quote_id = get_quote_id(quote_text)
                        likes = database.get_quote_likes(quote_id)
                        liked = database.is_already_liked(uid, quote_id)
                        quote = {
                            "text": quote_text,
                            "id": quote_id,
                            "likes": likes,
                            "comments": database.get_latest_comments(quote_id, 10),
                            "liked": liked
                        }
                        quotes.append(quote)
                    book["quotes"] = quotes
        except Exception as err:
            logger.exception(err)
        return res

    if results:
        step["body"] = {
            "results": [
                manage_quotes(available_results.get(res_name, ""))
                for res_name in results
            ]
        }
    else:
        step["body"] = {"results": []}
    return step


# REST API specifications
@router.post("/comments", response_model=Comment, tags=["Quiz"])
# @check_auth('txt_quiz')
async def comment_quote(request):
    """
    Апи для создания комментариев
    """
    quote_id = request.json["quote_id"]
    ok, msg = validate_quote_id(quote_id)
    if not ok:
        response_data = {"status": "Bad request", "quote_id": msg}
        return response_data, 400

    content = request.json["content"]
    ok, msg = validate_comment_body(content)
    if not ok:
        response_data = {"status": "Bad request", "content": msg}
        return response_data, 400

    passage_id, _ = get_txt_quiz_user_id_token()
    if database.is_already_commented(passage_id, quote_id):
        response_data = {"status": "Bad request", "quote_id": f"You have already commented quote with id '{quote_id}'"}
        return response_data, 400

    ok, msg = database.add_comment(passage_id, quote_id, content)
    if not ok:
        response_data = {'status': 'Server Error', 'message': msg}
        return response_data, 500

    return {'status': 'OK', 'message': 'Successfully commented quote'}, 201


@router.get("/comments", tags=["Quiz"])
# @check_auth('txt_quiz')
async def get_quote_comments(request):
    """
    Листинг комментариев
    """
    ok, limit = validate_limit(request.args.get('limit', "20"))
    if not ok:
        response_data = {'limit': "Is not valid integer"}
        return response_data, 400

    ok, offset = validate_limit(request.args.get('offset', "0"))
    if not ok:
        response_data = {'offset': "Is not valid integer"}
        return response_data, 400

    quote_id = request.args.get('qid', None)
    if quote_id is None:
        response_data = {'qid': 'GET parameter expected in URI'}
        return response_data, 400

    ok, msg = validate_quote_id(quote_id)
    if not ok:
        response_data = {"status": "Bad request", "quote_id": msg}
        return response_data, 400

    comments = database.get_quote_comments(quote_id, limit, offset)

    return {"results": comments}, 200


@router.post("/like", response_model=LikePostBody, tags=["Quiz"])
# @check_auth('txt_quiz')
async def likes_handler(request: LikePostBody):
    quote_id = request.json["quote_id"]

    if not validate_quote_id(quote_id):
        response_data = {"status": "Bad request", "quote_id": f"'{quote_id}' is not valid quote id"}
        return response_data, 400

    result = {"status": "Bad result", "quote_id": quote_id}
    logger.debug(f'User liked quote with id={quote_id}')
    uid, _ = get_txt_quiz_user_id_token()
    liked = database.is_already_liked(uid, quote_id)
    if liked:
        likes = database.get_quote_likes(quote_id)
        result = {"status": "Already liked", "quote_id": quote_id, "likes": likes, "liked": True}
    else:
        likes = database.increment_quote_likes(quote_id)
        if likes:
            database.add_user_like(uid, quote_id)
            result = {"status": "OK", "quote_id": quote_id, "likes": likes, "liked": True}
    return result


@router.post("/step", tags=["Quiz"])
# @check_auth('txt_quiz')
async def step_handler(request: StepPostBody):
    uid, _ = get_txt_quiz_user_id_token()
    logger.debug(f'uid={uid}')
    user_state = database.get_state(uid)
    draft = drafts.get_draft()
    availible_values = drafts.get_values()
    steps = draft["steps"]
    step_data = copy.deepcopy(request.json["responses"])

    if not ("steps_stack" in user_state):
        user_state["steps_stack"] = copy.deepcopy(
            draft["router_politics"]["steps_stack"]
        )

    if not user_state["steps_stack"]:
        return "Out of steps_stack", 404

    # Udp steps_stack
    for ph_name, ph_res in step_data.items():
        for res in ph_res:
            if not res.get("value"):
                continue
            if res.get("value") in availible_values:
                val = availible_values[res["value"]]
                res["value"] = val
                if isinstance(val, dict) and isinstance(
                        val.get("next_steps", ""), list
                ):
                    user_state["steps_stack"] = [
                                                    step
                                                    for step in val["next_steps"]
                                                    if step not in user_state["steps_stack"]
                                                ] + user_state["steps_stack"]
                    logger.debug(f'Upd steps_stack, add {val["next_steps"]} steps')
            else:
                res = f"A value = {res.get('value')} is not available"
                logger.warn(res)
                return res, 400

    # Get next step

    if not ("steps_trace" in user_state):
        user_state["steps_trace"] = []
    user_state["steps_trace"].append(user_state["steps_stack"].pop(0))
    next_step = steps[user_state["steps_trace"][-1]]

    # Udp2 steps_stack
    user_state["steps_stack"] = [
                                    step
                                    for step in next_step.get("next_steps", [])
                                    if step not in user_state["steps_stack"]
                                ] + user_state["steps_stack"]
    logger.debug(f'user_state["steps_trace"]={user_state["steps_trace"]}')
    logger.debug(f'user_state["steps_stack"]={user_state["steps_stack"]}')
    logger.debug(f'upd steps_stack, add {next_step.get("next_steps", [])} steps')

    # Save user state in db
    database.udp_state(uid, user_state)
    prev_step = user_state["steps_trace"][-2] if len(user_state["steps_trace"]) > 1 else ""
    step_data_id = database.add_step(
        uid,
        prev_step,
        {"raw_responses": request.json["responses"], "responses": step_data},
        {},
        drafts.current_draft_name,
        steps.get(prev_step, {}).get("stats", [])
    )
    database.add_tracking(step_data_id, request.json["tracking"], {})

    # Prepare response
    next_step = copy.deepcopy(next_step)
    logger.debug(f'pre_next_step:={next_step}')
    for handler in next_step.get("handlers", []):
        if handler.get("name") in handlers:
            next_step = handlers[handler.get("name")](
                *handler.get("args", []),
                draft=draft,
                next_step=next_step,
                uid=uid,
                database=database,
                **handler.get("kwargs", {}),
            )

    if "handlers" in next_step:
        del next_step["handlers"]
    if "next_steps" in next_step:
        del next_step["next_steps"]
    if "stats" in next_step:
        del next_step["stats"]
    if "body_hidden_keys" in next_step:
        for k in next_step["body_hidden_keys"]:
            del next_step["body_hidden_keys"][k]

    logger.debug(f'next_step:={next_step}')

    return next_step


# Отзывы
@router.post("/feedback", response_model=Feedback, tags=["Quiz"])
# @check_auth('txt_quiz')
async def feedbacks_handler(request):
    """Приём отзывов"""
    passage_id, _ = get_txt_quiz_user_id_token()
    email = request.json["email"]
    name = request.json["name"]
    main_text = request.json["main_text"]
    logger.debug(f'Пришел отзыв от id:{passage_id} '
                 f'name: {name} '
                 f'email:{email} '
                 f'main_text:{main_text} ')
    # Валидация
    if not is_mail_valid(email):
        response_data = {"type": "message", "result": f'"{email}" является некорректной почтой'}
        return response_data, 400
    if len(name) < 2:
        response_data = {"type": "message", "result": f'Имя "{name}" - слишком короткое'}
        return response_data, 400
    if len(main_text) < 1:
        response_data = {"type": "message", "result": f'Сообщение "{main_text}" слишком короткое'}
        return response_data, 400
    # Запись отзыва в БД
    logger.debug("Отправляем отзыв в БД")
    success, msg = database.add_feedback(passage_id=int(passage_id),
                                         email=email,
                                         name=name,
                                         main_text=main_text
                                         )
    logger.debug(f'Ответ от БД {msg}')
    if not success:
        response_data = {"type": "message", "result": msg}
        return response_data, 400
    return {"type": "message", "result": "OK"}
