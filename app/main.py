"""Calculadora simple con FastAPI: historial y exportación a JSON."""
import ast
import json
import operator
import os
from datetime import datetime
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
EXPORT_DIR = Path(os.getenv("EXPORT_DIR", BASE_DIR / "exports"))
STATIC_DIR = Path(__file__).resolve().parent / "static"
HISTORY_FILE = DATA_DIR / "history.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


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


def _read_history() -> list:
    if HISTORY_FILE.exists():
        try:
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []
    return []


def _write_history(items: list) -> None:
    HISTORY_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------- App ----------
app = FastAPI(title="Calculadora")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class CalcIn(BaseModel):
    expression: str


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/login")
def login_redirect():
    # Compatibilidad con enlaces antiguos: el login ya no existe.
    return RedirectResponse("/")


@app.post("/api/calculate")
def calculate(body: CalcIn):
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
        items = _read_history()
        items.append(entry)
        _write_history(items)
    return entry


@app.get("/api/history")
def history():
    with _lock:
        return {"history": _read_history()}


@app.delete("/api/history")
def clear_history():
    with _lock:
        _write_history([])
    return {"ok": True}


@app.post("/api/save")
def save_history():
    """Exporta el historial a un .json en la carpeta local exports/."""
    with _lock:
        items = _read_history()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"historial_{stamp}.json"
    payload = {
        "exportado": datetime.now().isoformat(timespec="seconds"),
        "total": len(items),
        "historial": items,
    }
    (EXPORT_DIR / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "file": f"exports/{filename}", "total": len(items)}
