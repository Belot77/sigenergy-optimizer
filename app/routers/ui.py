from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

ui = APIRouter()
templates = Jinja2Templates(directory="templates")


@ui.get("/", response_class=HTMLResponse)
async def index(request: Request):
    ingress_path = request.headers.get("X-Ingress-Path", "").rstrip("/")
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"ingress_path": ingress_path},
    )
