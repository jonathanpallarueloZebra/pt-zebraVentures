# planificador_turnos-backend
## Requisitos
- Python 3.12+
- PostgreSQL

## Instalación
```bash
# Crear entorno virtual
python -m venv venv

# Activar entorno virtual
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuración
El archivo `.env` se genera automáticamente al clonar desde el generador.

## Base de datos local (dev)
La base de datos de desarrollo se crea desde el panel del generador de proyectos (sección "Base de datos de desarrollo").
El archivo `.env` ya contiene las credenciales configuradas.

## Ejecución
```bash
# Ejecutar migraciones
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Iniciar servidor
python manage.py runserver
```

## Docker
```bash
docker build -t <IMAGE_NAME> .
docker push <IMAGE_NAME>
```

## API Docs
Documentación disponible en: `http://localhost:8000/api/docs/`

## Autenticación
| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/auth/register/` | POST | Registro de usuario |
| `/api/auth/login/` | POST | Login (devuelve tokens JWT) |
| `/api/auth/refresh/` | POST | Refrescar access token |
| `/api/auth/profile/` | GET/PUT | Perfil del usuario |

## Agente IA
Modelo: `gpt-5-mini`

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/agent/chat/` | POST | Enviar mensaje al agente |
