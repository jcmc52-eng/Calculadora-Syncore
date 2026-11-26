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
docker run --rm -p 8080:8080 --env-file .env -v "${PWD}/exports:/app/exports" -v "${PWD}/data:/app/data" calculadora
```
Abrir http://localhost:8080. Los volúmenes hacen que los `.json` exportados queden en la carpeta local `exports/`.

## Desplegar en Google Cloud Run
El contenedor escucha en la variable `PORT` que entrega Cloud Run (8080). El archivo `.env` **no** va en la imagen, así que en el servicio hay que definir estas variables (Editar revisión → Variables y secretos), idealmente desde Secret Manager:

| Variable | Obligatoria | Uso |
|---|---|---|
| `APP_PASSWORD` | Sí | Clave de ingreso. Sin ella el contenedor no arranca. |
| `APP_USER` | No (por defecto `admin`) | Usuario de ingreso |
| `SECRET_KEY` | Recomendada | Firma de la cookie de sesión; si falta, las sesiones se pierden al reiniciar o con varias instancias |

En Cloud Run el disco es temporal: `data/` y `exports/` se borran cuando la instancia se reinicia.

## Estructura
- `app/main.py` — API FastAPI (login, cálculo seguro, historial, exportación)
- `app/static/` — interfaz (login, calculadora, historial)
- `data/history.json` — historial guardado por usuario
- `exports/` — archivos generados con el botón Save
