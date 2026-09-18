# PT Zebra — Planificador de Turnos

Producto de **Zebra Ventures** para planificar los turnos semanales de una plantilla
repartida en varias tiendas, con generación automática que respeta las restricciones
del convenio y de cada empresa.

> Fork limpio del planificador validado en producción con Cabrero e Hijos. Cabrero y
> PT Zebra son repositorios **independientes**: cada uno arregla lo suyo.

---

## Estructura del monorepo

```
backend/     Django 5.1 + DRF, servido por uvicorn. API bajo /api/
frontend/    Angular 19 standalone, signals-first
openspec/    Fuente de verdad del comportamiento (specs) y cambios en curso
despliegue/  Ficheros .env de ejemplo por entorno
scripts/     Construcción de imágenes y despliegue
```

## Arquitectura

El frontend **no** conoce la URL del backend: llama a la ruta relativa `/api` y el
nginx que va dentro del propio contenedor del front hace de proxy hacia el servicio
`backend`. Consecuencias:

- El balanceador de delante (Traefik) enruta **un solo contenedor**, el del front.
- El backend no se publica al exterior (`expose: 8000`, sin puerto mapeado).
- **No hay CORS** entre front y back: para el navegador todo es el mismo origen.

```
navegador ──► Traefik ──► contenedor frontend (nginx)
                               ├── /api/  ──► backend:8000
                               └── resto  ──► index.html (SPA Angular)
```

## Marca configurable

La app `branding` guarda en base de datos el nombre, logo, favicon y colores de cada
instalación — un registro por despliegue. **La marca no se hardcodea**: personalizar
una instalación nueva es cargar datos, no tocar código.

## Entornos

QA y producción tienen **bases de datos separadas**. Toda la configuración entra por
variables de entorno; no hay ningún `.env` en el repositorio.

## Puesta en marcha (desarrollo)

```bash
# Backend
cd backend
python -m venv venv && source venv/Scripts/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp ../despliegue/env.dev.ejemplo .env.dev             # y rellenar
python manage.py migrate
python manage.py runserver

# Frontend
cd frontend
npm ci
npm start
```

## Tests

```bash
cd backend  && pytest
cd frontend && npm test
```

## Documentación

- `openspec/config.yaml` — contexto del proyecto y reglas de trabajo
- `openspec/specs/` — comportamiento especificado por módulo
- `DESPLIEGUE.md` — construir imágenes y desplegar en QA/producción
