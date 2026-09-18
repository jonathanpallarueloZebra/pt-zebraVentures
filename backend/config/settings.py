import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load the right .env file based on ENVIRONMENT (default: dev)
_env = os.getenv('ENVIRONMENT', 'dev')
_env_file = Path(__file__).resolve().parent.parent / f'.env.{_env}'
if _env_file.exists():
    load_dotenv(_env_file)
else:
    load_dotenv()  # fallback

BASE_DIR = Path(__file__).resolve().parent.parent

# Sin valor por defecto en los despliegues: una clave escrita aqui acaba en el
# repositorio y sirve para firmar sesiones y tokens de cualquier despliegue que
# se olvide de definirla. Los .env de QA y produccion llevan una propia,
# distinta cada uno.
#
# En los tests se usa una fija: pytest no pasa por ningun .env y el valor no
# sale de la maquina que los ejecuta.
_EJECUTANDO_TESTS = 'PYTEST_CURRENT_TEST' in os.environ or 'pytest' in sys.argv[0]
if _EJECUTANDO_TESTS:
    SECRET_KEY = os.getenv('SECRET_KEY', 'clave-solo-para-tests-no-usar-en-despliegues')
else:
    SECRET_KEY = os.environ['SECRET_KEY']

DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 'yes')

# La MISMA imagen sirve a varios clientes (valentia, cabrero-planificador-qa...) y
# nginx proxea /api/ conservando el Host del navegador (proxy_set_header Host
# $host). Es decir: lo que Django valida aqui es el dominio del FRONTEND, uno
# distinto por despliegue. Cuando ALLOWED_HOSTS solo listaba el de valentia, en
# cabrero todos los endpoints devolvian 400 (DisallowedHost) con la misma imagen.
#
# El punto inicial de '.zebraventures.eu' es la sintaxis de comodin de Django:
# casa el dominio y CUALQUIER subdominio, asi que un despliegue nuevo funciona sin
# tocar configuracion. Se une siempre a lo que traiga la variable en vez de ser
# solo un valor por defecto, porque los despliegues ya la definen con una lista
# propia (y era justo esa lista la que se dejaba fuera su propio dominio).
#
# Sigue siendo una politica cerrada: nada fuera de zebraventures.eu se acepta, y
# es la misma superficie que ya se confia en CORS_ALLOWED_ORIGIN_REGEXES.
_allowed = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '').split(',') if h.strip()]
for _h in ('.zebraventures.eu', 'localhost', '127.0.0.1'):
    if _h not in _allowed:
        _allowed.append(_h)
ALLOWED_HOSTS = _allowed

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party,
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt',
    # Local apps,
    'apps.authentication',
    'apps.users',
    'apps.agent',
    'drf_spectacular',
    'apps.email_service',
    'apps.catalog',
    'apps.core',
    'apps.workers',
    'apps.rest_days',
    'apps.restrictions',
    'apps.planning',
    'apps.absences',
    'apps.branding',
    'apps.dynamic_fields',
    'apps.shifts',
    'apps.shift_days',
    'apps.assignments',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Add Elastic APM only in non-dev environments
if os.getenv('ENVIRONMENT', 'dev') != 'dev':
    INSTALLED_APPS.append('elasticapm.contrib.django')
    MIDDLEWARE.append('elasticapm.contrib.django.middleware.TracingMiddleware')

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', ''),
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        # Sin valor por defecto a proposito: una IP aqui haria que un .env
        # incompleto conectase en silencio contra el servidor de Arcis.
        'HOST': os.getenv('DB_HOST', ''),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Detrás del proxy/balanceador de GCP la peticion llega como HTTP interno, asi
# que sin esto request.build_absolute_uri() genera URLs http:// aunque el sitio
# se sirva por https. Eso rompia el favicon de branding: el navegador descarta
# un <link rel="icon"> http:// dentro de una pagina https (mixed content) sin
# avisar, mientras que el logo (un <img>) si sigue el redirect 302 y se veia.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

ENVIRONMENT = os.getenv('ENVIRONMENT', 'dev')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

AUTH_USER_MODEL = 'authentication.CustomUser'

# CORS
# Lista explícita de orígenes: CORS_ALLOWED_ORIGINS (coma-separado) o, si no,
# FRONTEND_URL (compatibilidad) o localhost.
_cors_origins = os.getenv(
    'CORS_ALLOWED_ORIGINS',
    os.getenv('FRONTEND_URL', 'http://localhost:4200'),
)
CORS_ALLOWED_ORIGINS = [o.strip() for o in _cors_origins.split(',') if o.strip()]

# Además, permite por regex cualquier subdominio de zebraventures.eu (QA, prod,
# previews…) y localhost en cualquier puerto. Esto evita que el login se rompa
# por un origen que falte en la lista explícita de un entorno concreto.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https://[a-z0-9-]+\.zebraventures\.eu$',
    r'^http://localhost(:\d+)?$',
    r'^http://127\.0\.0\.1(:\d+)?$',
]

SPECTACULAR_SETTINGS = {
    'TITLE': 'planificador_turnos-backend API',
    'DESCRIPTION': 'API documentation',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# ── Elastic APM ──
if ENVIRONMENT != 'dev':
    ELASTIC_APM = {
        'SERVICE_NAME': os.getenv('APM_SERVICE_NAME', 'planificador_turnos-backend'),
        'SERVER_URL': os.getenv('APM_SERVER_URL', 'http://82.223.29.91:8200'),
        'SECRET_TOKEN': os.getenv('APM_SECRET_TOKEN', ''),
        'ENVIRONMENT': os.getenv('APM_ENVIRONMENT', ENVIRONMENT),
        'DEBUG': DEBUG,
        'CAPTURE_BODY': os.getenv('APM_CAPTURE_BODY', 'errors'),
        'CAPTURE_HEADERS': os.getenv('APM_CAPTURE_HEADERS', 'True').lower() in ('true', '1', 'yes'),
        'TRANSACTION_SAMPLE_RATE': float(os.getenv('APM_TRANSACTION_SAMPLE_RATE', '1.0')),
    }

# ── Logging ──
_log_level = os.getenv('LOG_LEVEL', 'INFO')
_elk_enabled = os.getenv('ELK_ENABLED', 'false').lower() in ('true', '1', 'yes')
_file_enabled = os.getenv('LOG_FILE_ENABLED', 'false').lower() in ('true', '1', 'yes')

_log_handlers_cfg = {
    'console': {
        'class': 'logging.StreamHandler',
        'formatter': 'verbose',
        'level': _log_level,
    },
}
_active_handlers = ['console']

if ENVIRONMENT != 'dev':
    _log_handlers_cfg['elasticapm'] = {
        'class': 'elasticapm.contrib.django.handlers.LoggingHandler',
        'level': 'ERROR',
    }
    _active_handlers.append('elasticapm')

if _elk_enabled:
    _log_handlers_cfg['elasticsearch'] = {
        '()': 'config.log_handlers.ElasticsearchLogHandler',
        'level': 'WARNING',
    }
    _active_handlers.append('elasticsearch')

if _file_enabled:
    import pathlib as _pl
    _log_file_path = os.getenv('LOG_FILE_PATH', 'logs/app.log')
    _pl.Path(_log_file_path).parent.mkdir(parents=True, exist_ok=True)
    _log_handlers_cfg['file'] = {
        'class': 'logging.handlers.TimedRotatingFileHandler',
        'filename': _log_file_path,
        'when': 'midnight',
        'backupCount': 7,
        'formatter': 'verbose',
        'level': _log_level,
    }
    _active_handlers.append('file')

# Sin esto Django aplica su DEFAULT_LOGGING, cuyo handler de consola lleva el
# filtro require_debug_true: en produccion (DEBUG=False) los tracebacks de los
# 500 se escriben SOLO en mail_admins y, al no haber ADMINS, se pierden. El
# resultado era un 500 opaco en el navegador y ni una linea en los logs del
# contenedor. Aqui la consola no se filtra por DEBUG, asi que el traceback
# siempre queda en la salida estandar (docker compose logs backend).
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': _log_handlers_cfg,
    'root': {
        'handlers': _active_handlers,
        'level': _log_level,
    },
    'loggers': {
        'django': {
            'handlers': _active_handlers,
            'level': _log_level,
            'propagate': False,
        },
        # django.request es el logger que emite el traceback de cada 500.
        # Necesita nivel ERROR explicito para no depender de LOG_LEVEL.
        'django.request': {
            'handlers': _active_handlers,
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'elasticapm': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'elasticapm.errors': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
