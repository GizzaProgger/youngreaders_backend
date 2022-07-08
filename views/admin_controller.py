from fastapi import APIRouter
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

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
