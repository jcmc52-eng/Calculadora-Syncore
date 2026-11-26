# Calculadora (FastAPI + Uvicorn)

Calculadora simple con UI redondeada, inicio de sesión, historial persistente y botón **Save** que exporta el historial a `exports/historial_<usuario>_<fecha>.json`.

## Credenciales
El usuario y la clave están en el archivo `.env` (`APP_USER` / `APP_PASSWORD`). Cámbialos ahí si quieres.

## Ejecutar local
```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```
Abrir http://localhost:8000

## Ejecutar con Docker
```powershell
docker build -t calculadora .
docker run --rm -p 8000:8000 --env-file .env -v "${PWD}/exports:/app/exports" -v "${PWD}/data:/app/data" calculadora
```
Los volúmenes hacen que los `.json` exportados queden en la carpeta local `exports/`.

## Estructura
- `app/main.py` — API FastAPI (login, cálculo seguro, historial, exportación)
- `app/static/` — interfaz (login, calculadora, historial)
- `data/history.json` — historial guardado por usuario
- `exports/` — archivos generados con el botón Save
