#!/bin/sh
# Aplica las migraciones contra la base que el entorno tenga configurada (DB_HOST,
# DB_NAME...) antes de arrancar el servidor.
#
# Sin esto nadie las aplicaba: el CMD solo lanzaba uvicorn y ni el compose ni los
# despliegues traian un paso de migrate. Asi llego a produccion el modelo Branding
# con date_picker_mode pero sin su columna en la BD, y /api/branding/ devolvia 500
# (ProgrammingError: column branding_branding.date_picker_mode does not exist).
#
# migrate es idempotente: si no hay nada pendiente no toca la base.
set -e

# Solo se migra al arrancar el servidor. Asi un `docker run <img> python manage.py
# dbshell` o un `compose run` puntual no dispara migraciones de rebote.
case "$1" in
    uvicorn|gunicorn|daphne)
        retries="${MIGRATE_RETRIES:-10}"
        delay="${MIGRATE_RETRY_DELAY:-3}"
        attempt=1
        while true; do
            echo "entrypoint: aplicando migraciones (intento $attempt/$retries)"
            if python manage.py migrate --noinput; then
                break
            fi
            if [ "$attempt" -ge "$retries" ]; then
                echo "entrypoint: migrate fallo tras $attempt intentos; abortando" >&2
                exit 1
            fi
            # Casi siempre es que la BD aun no acepta conexiones. Se reintenta en
            # vez de arrancar con un esquema desfasado y servir 500 en silencio.
            echo "entrypoint: migrate fallo; reintento en ${delay}s" >&2
            attempt=$((attempt + 1))
            sleep "$delay"
        done
        ;;
esac

# exec para que el servidor quede como PID 1 y reciba el SIGTERM de `docker stop`.
exec "$@"
