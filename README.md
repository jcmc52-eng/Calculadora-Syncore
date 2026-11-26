# Calculadora (FastAPI + Uvicorn)

Calculadora simple con UI redondeada, historial persistente y botón **Save** que exporta el historial a `exports/historial_<fecha>.json`. No requiere inicio de sesión.

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
docker run --rm -p 8080:8080 -v "${PWD}/exports:/app/exports" -v "${PWD}/data:/app/data" calculadora
```
Abrir http://localhost:8080. Los volúmenes hacen que los `.json` exportados queden en la carpeta local `exports/`.

## Desplegar en Google Cloud Run
El contenedor escucha en la variable `PORT` que entrega Cloud Run (8080). No necesita variables de entorno.

En Cloud Run el disco es temporal: `data/` y `exports/` se borran cuando la instancia se reinicia, y cada instancia tiene su propio historial.

## Estructura
- `app/main.py` — API FastAPI (cálculo seguro, historial, exportación)
- `app/static/` — interfaz (calculadora e historial)
- `data/history.json` — historial guardado
- `exports/` — archivos generados con el botón Save
