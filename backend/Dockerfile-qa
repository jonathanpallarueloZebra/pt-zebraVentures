FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    pkg-config \
    curl \
    wget \
    dnsutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .


# Entrypoint: aplica las migraciones pendientes antes de arrancar uvicorn.
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
# sed sobre CRLF: si el script llega desde un checkout Windows (core.autocrlf)
# el shebang seria '#!/bin/sh' + CR y el exec fallaria con "no such file or
# directory". Aqui es solo prevencion; el fichero del repo ya esta en LF.
RUN sed -i 's/\r$//' /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

EXPOSE 8000

CMD ["uvicorn", "config.asgi:application", "--host", "0.0.0.0", "--port", "8000"]
