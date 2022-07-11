from fastapi import APIRouter
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from models.notify_post import NotifyPostBody
from services.middlewares import check_auth
from utils.smtp import Email

router = APIRouter(prefix="/admin", tags=["Admin"])

templates = Jinja2Templates(directory="static/templates/")


@router.get("/v1", response_class=HTMLResponse)
def get_admin_v1():
    return templates.TemplateResponse("admin_index.html",
                                      {})


@router.get("/admin/v2", response_class=HTMLResponse)
@router.get("/admin/v2/<path:path>")
def get_admin_v2(path=''):
    return templates.TemplateResponse("admin_v2_index.html",
                                      {})


@router.post("/email", tags=["Admin"])
# @check_auth("admin")
async def send_email(request: NotifyPostBody):
    data = request.json
    receiver_email = data.get("receiver_email")
    topic = data.get("topic")
    message = data.get("message")
    email = Email(receiver_email)
    if email.valid_email():
        await email.send_email(subject=topic, body=message)
        return "Success", 200
    else:
        return "Invalid email", 406
