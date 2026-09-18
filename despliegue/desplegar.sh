#!/usr/bin/env bash
#
# Despliegue de PT ZEBRA en arcis. Va EN EL SERVIDOR, en
# /opt/docker/projects/ptzebra/desplegar.sh
#
# Sigue el patrón que ya usan los demás proyectos de la máquina (ver
# `adea/desplegar.sh`): mismo sitio, mismas validaciones y la misma solución al
# lío de las credenciales de Docker.
#
# Es el único comando que la clave SSH de GitHub puede ejecutar: en
# ~/.ssh/authorized_keys la clave se restringe con
#
#     command="/opt/docker/projects/ptzebra/desplegar.sh",no-port-forwarding,
#     no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA...
#
# Con eso, aunque alguien se hiciera con la clave, no obtiene una shell en la
# máquina: solo puede lanzar este script. Y este script solo toca PT Zebra.
# Importa porque arcis es compartida: unos noventa contenedores de otros
# clientes.
#
# Uso (lo invoca el workflow, no una persona):
#     desplegar.sh <entorno> <tag> [commit]
# Ejemplo:
#     desplegar.sh qa 0.1.0-qa

set -euo pipefail

DIRECTORIO="/opt/docker/projects/ptzebra"

# Config de Docker propio del proyecto, con el token de lectura de ghcr.io.
#
# Va aparte del /root/.docker/config.json a proposito: ese fichero es compartido
# con los demas proyectos de la maquina y tiene un credHelpers de gcloud que
# ANULA credenciales de otros registries y hace fallar el pull con `denied`
# (a ADEA le costo tres intentos dar con ello). Con un config propio, PT Zebra
# no depende de lo que haya ahi ni lo modifica.
#
# Se crea una sola vez en el servidor:
#   docker --config /opt/docker/projects/ptzebra/.docker #     login ghcr.io -u <usuario> --password-stdin <<< "<token con read:packages>"
CONFIG_DOCKER="$DIRECTORIO/.docker"

# Cuando la clave lleva `command=`, SSH ignora lo que pida el cliente y guarda
# la orden original aquí. Se lee de ahí para que el restrictor no se pueda
# esquivar mandando otro comando.
if [ -n "${SSH_ORIGINAL_COMMAND:-}" ]; then
  # shellcheck disable=SC2086
  set -- $SSH_ORIGINAL_COMMAND
fi

ENTORNO="${1:-}"
TAG="${2:-}"
COMMIT="${3:-}"

# ── Validaciones ────────────────────────────────────────────────────────────
# Todo lo que llega de fuera se comprueba antes de usarlo. Sin esto, un valor
# como `qa; rm -rf /` acabaría interpolado en un comando.

case "$ENTORNO" in
  qa|prod) ;;
  *) echo "ERROR: entorno debe ser 'qa' o 'prod', no '$ENTORNO'" >&2; exit 1 ;;
esac

# Mismo formato que ADEA: sin `v` inicial y con el entorno como sufijo.
if ! echo "$TAG" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+-(qa|prod)$'; then
  echo "ERROR: tag mal formado: '$TAG'. Se espera X.Y.Z-qa o X.Y.Z-prod" >&2
  exit 1
fi

# El sufijo del tag y el entorno tienen que coincidir: desplegar una imagen -qa
# en producción sería un desastre silencioso. En PT Zebra producción lleva los
# turnos reales de la gente.
if [ "${TAG##*-}" != "$ENTORNO" ]; then
  echo "ERROR: el tag '$TAG' no corresponde al entorno '$ENTORNO'" >&2
  exit 1
fi

COMPOSE="$DIRECTORIO/docker-compose.$ENTORNO.yml"
ENV_FILE="$DIRECTORIO/.env.$ENTORNO"
PROYECTO="ptzebra-$ENTORNO"

[ -f "$COMPOSE" ]  || { echo "ERROR: no existe $COMPOSE" >&2; exit 1; }
[ -f "$ENV_FILE" ] || { echo "ERROR: no existe $ENV_FILE" >&2; exit 1; }
[ -f "$CONFIG_DOCKER/config.json" ] || { echo "ERROR: no existe $CONFIG_DOCKER/config.json" >&2; exit 1; }

cd "$DIRECTORIO"

echo "==> Desplegando $TAG en $ENTORNO"

# ── Copia de seguridad del .env ─────────────────────────────────────────────
# Contiene los secretos y se va a modificar. Si algo sale mal, se vuelve a él.
cp "$ENV_FILE" "$ENV_FILE.bak-$(date +%F-%H%M%S)"

# Solo se toca la línea de versión. Nada más del .env se modifica.
sed -i "s|^VERSION=.*|VERSION=$TAG|" "$ENV_FILE"

# El commit solo se escribe si viene, y se añade si la línea aún no existe.
if [ -n "$COMMIT" ]; then
  # Solo hexadecimal: lo que llega de fuera acaba dentro de un `sed`.
  if ! echo "$COMMIT" | grep -qE '^[0-9a-f]{7,40}$'; then
    echo "ERROR: commit mal formado: '$COMMIT'" >&2
    exit 1
  fi
  if grep -qE '^COMMIT=' "$ENV_FILE"; then
    sed -i "s|^COMMIT=.*|COMMIT=$COMMIT|" "$ENV_FILE"
  else
    echo "COMMIT=$COMMIT" >> "$ENV_FILE"
  fi
fi

echo "==> Versión en $ENV_FILE:"
grep -E '^VERSION=' "$ENV_FILE"

# ── Despliegue ──────────────────────────────────────────────────────────────
# SIEMPRE con -p y -f. Sin ellos, docker compose actuaría sobre lo que crea que
# es «el proyecto de esta carpeta» y podría apagar otra cosa.
docker --config "$CONFIG_DOCKER" compose -p "$PROYECTO" -f "$COMPOSE" --env-file "$ENV_FILE" pull
docker --config "$CONFIG_DOCKER" compose -p "$PROYECTO" -f "$COMPOSE" --env-file "$ENV_FILE" up -d

# ── Comprobación ────────────────────────────────────────────────────────────
# Un contenedor `unhealthy` es INVISIBLE para Traefik: el dominio devuelve un
# 404 mudo, sin rastro en los logs del proxy. Por eso se espera y se verifica.
echo "==> Esperando a que los contenedores estén sanos..."

# Se comprueban los dos POR SU NOMBRE EXACTO. El filtro `name` de Docker es por
# subcadena, no una expresión regular: contando coincidencias podrían colarse
# los del OTRO entorno y dar por bueno un despliegue que falló.
ESPERADOS="ptzebra-backend-$ENTORNO ptzebra-frontend-$ENTORNO"

# El backend aplica migraciones al arrancar, así que la primera vez tarda más
# que en otros proyectos: 30 intentos son dos minutos y medio.
SANOS=0
for _ in $(seq 1 30); do
  SANOS=0
  for c in $ESPERADOS; do
    ESTADO=$(docker inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null || echo ausente)
    [ "$ESTADO" = "healthy" ] && SANOS=$((SANOS + 1))
  done
  [ "$SANOS" -eq 2 ] && break
  # El sleep va DESPUÉS de comprobar: si ya están sanos no se esperan 5s de más.
  sleep 5
done

echo "==> Estado final:"
docker ps --filter "name=ptzebra-" --format '{{.Names}}\t{{.Status}}'

if [ "$SANOS" -ne 2 ]; then
  echo "ERROR: los contenedores de $ENTORNO no llegaron a healthy" >&2
  for c in $ESPERADOS; do
    echo "  $c -> $(docker inspect -f '{{.State.Health.Status}}' "$c" 2>/dev/null || echo ausente)" >&2
  done
  docker --config "$CONFIG_DOCKER" compose -p "$PROYECTO" -f "$COMPOSE" --env-file "$ENV_FILE" logs --tail=40
  exit 1
fi

echo "==> Despliegue de $TAG en $ENTORNO completado"
