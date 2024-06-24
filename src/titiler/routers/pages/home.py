from fastapi import Depends, APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from markdown import markdown

router = APIRouter()
templates = Jinja2Templates(directory="src/static")


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    # Read the markdown file
    with open(Path("src/static/home/home.md")) as f:
        md_content = f.read()

    # Convert markdown to HTML
    html_content = markdown(md_content)

    return templates.TemplateResponse(
        "home/home.html",
        {
            "request": request,
            "content": html_content,
        },
    )
