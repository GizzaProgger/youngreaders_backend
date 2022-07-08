from fastapi import APIRouter

router = APIRouter(prefix="/static", tags=["Static"])


@router.get("/{path}")
def static_out(path):
    # Traefik ?
    ...
    # return send_from_directory(f"static/{path}", path)
