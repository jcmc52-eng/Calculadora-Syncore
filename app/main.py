"""Calculadora simple con FastAPI: login, historial y exportación a JSON."""
import ast
import hashlib
import hmac
import json
import logging
import operator
import os
import secrets
from datetime import datetime
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", BASE_DIR / "exports"))
STATIC_DIR = Path(__file__).resolve().parent / "static"
HISTORY_FILE = DATA_DIR / "history.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


def _load_env(path: Path) -> None:
    """Carga un .env sencillo (KEY=VALUE) sin dependencias extra."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


_load_env(BASE_DIR / ".env")

APP_USER = os.getenv("APP_USER", "admin")
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)

if not APP_PASSWORD:
    # No detenemos el servidor (Cloud Run lo marcaría como caído); sólo se bloquea el login.
    logging.getLogger("uvicorn.error").warning(
        "APP_PASSWORD no está definida: el inicio de sesión queda deshabilitado. "
        "Defínela en .env o como variable de entorno."
    )

# Guardamos sólo el hash de la clave en memoria.
_SALT = secrets.token_bytes(16)
_PWD_HASH = hashlib.pbkdf2_hmac("sha256", APP_PASSWORD.encode(), _SALT, 200_000)


def verify_password(password: str) -> bool:
    if not APP_PASSWORD:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), _SALT, 200_000)
    return hmac.compare_digest(candidate, _PWD_HASH)


# ---------- Evaluador seguro de expresiones ----------
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def safe_eval(expr: str) -> float:
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = _eval(node.left), _eval(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 100:
                raise ValueError("Exponente demasiado grande")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval(node.operand))
        raise ValueError("Expresión no válida")

    if len(expr) > 200:
        raise ValueError("Expresión demasiado larga")
    expr = expr.replace("×", "*").replace("÷", "/").replace("^", "**")
    return _eval(ast.parse(expr, mode="eval"))


# ---------- Persistencia del historial ----------
_lock = Lock()


def _read_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def _write_history(data: dict) -> None:
    HISTORY_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- App ----------
app = FastAPI(title="Calculadora")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="strict", max_age=8 * 3600)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def current_user(request: Request) -> str:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="No autenticado")
    return user


class LoginIn(BaseModel):
    username: str
    password: str


class CalcIn(BaseModel):
    expression: str


@app.get("/")
def index(request: Request):
    if not request.session.get("user"):
        return RedirectResponse("/login")
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login")
def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse("/")
    return FileResponse(STATIC_DIR / "login.html")


@app.post("/api/login")
def login(body: LoginIn, request: Request):
    if not APP_PASSWORD:
        raise HTTPException(status_code=503, detail="Login no configurado: falta APP_PASSWORD en el servidor")
    user_ok = hmac.compare_digest(body.username, APP_USER)
    pwd_ok = verify_password(body.password)
    if not (user_ok and pwd_ok):
        raise HTTPException(status_code=401, detail="Usuario o clave incorrectos")
    request.session["user"] = body.username
    return {"ok": True, "user": body.username}


@app.post("/api/logout")
def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    return {"user": current_user(request)}


@app.post("/api/calculate")
def calculate(body: CalcIn, request: Request):
    user = current_user(request)
    try:
        result = safe_eval(body.expression)
    except ZeroDivisionError:
        raise HTTPException(status_code=400, detail="División por cero")
    except (ValueError, SyntaxError, TypeError, OverflowError):
        raise HTTPException(status_code=400, detail="Expresión no válida")
    if isinstance(result, float) and result.is_integer():
        result = int(result)
    elif isinstance(result, float):
        result = round(result, 10)
    entry = {
        "expression": body.expression,
        "result": result,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    with _lock:
        data = _read_history()
        data.setdefault(user, []).append(entry)
        _write_history(data)
    return entry


@app.get("/api/history")
def history(request: Request):
    user = current_user(request)
    with _lock:
        return {"history": _read_history().get(user, [])}


@app.delete("/api/history")
def clear_history(request: Request):
    user = current_user(request)
    with _lock:
        data = _read_history()
        data[user] = []
        _write_history(data)
    return {"ok": True}


@app.post("/api/save")
def save_history(request: Request):
    """Exporta el historial del usuario a un .json en la carpeta local exports/."""
    user = current_user(request)
    with _lock:
        items = _read_history().get(user, [])
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"historial_{user}_{stamp}.json"
    payload = {
        "usuario": user,
        "exportado": datetime.now().isoformat(timespec="seconds"),
        "total": len(items),
        "historial": items,
    }
    (EXPORT_DIR / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "file": f"exports/{filename}", "total": len(items)}
