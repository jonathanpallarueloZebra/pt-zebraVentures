#!/usr/bin/env bash
#
# Devuelve la demo de QA a su estado de partida.
#
# Marketing enseña el planificador a clientes y durante la demo se tocan
# datos: se mueven turnos, se dan de alta ausencias, se regeneran planes. Este
# script deja la base como estaba para que la siguiente demo empiece igual que
# la anterior.
#
# Va EN EL SERVIDOR, en /opt/docker/projects/ptzebra/resetear-demo.sh
#
# A mano:
#     /opt/docker/projects/ptzebra/resetear-demo.sh
#
# Cada dos días a las 05:30 (crontab de root):
#     30 5 */2 * * /opt/docker/projects/ptzebra/resetear-demo.sh >> /var/log/ptzebra-demo.log 2>&1
#
# `seed_demo --reset` borra solo lo que lleva la marca `_demo` y lo vuelve a
# crear. No toca los usuarios: si los borrase, cada reseteo dejaría la demo sin
# nadie con quien entrar.

set -euo pipefail

CONTENEDOR="ptzebra-backend-qa"

# Las credenciales del administrador de la demo salen del .env.qa, que es el
# único sitio del servidor donde viven los secretos de este entorno. Así no hay
# una contraseña escrita en este script ni en el crontab.
ENV_FILE="/opt/docker/projects/ptzebra/.env.qa"

echo "=== $(date '+%F %T') reseteando la demo ==="

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTENEDOR"; then
  echo "ERROR: el contenedor $CONTENEDOR no está levantado" >&2
  exit 1
fi

# DEMO_ADMIN_* son opcionales: si no están en el .env.qa, seed_demo no toca
# ningún usuario y el reseteo sigue adelante igual.
ADMIN_EMAIL="$(grep -E '^DEMO_ADMIN_EMAIL=' "$ENV_FILE" | cut -d= -f2- || true)"
ADMIN_PASS="$(grep -E '^DEMO_ADMIN_PASSWORD=' "$ENV_FILE" | cut -d= -f2- || true)"

ARGS=(python manage.py seed_demo --reset)
if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASS" ]; then
  ARGS+=(--admin-email "$ADMIN_EMAIL" --admin-password "$ADMIN_PASS")
fi

docker exec "$CONTENEDOR" "${ARGS[@]}"

echo "=== $(date '+%F %T') demo reseteada ==="
