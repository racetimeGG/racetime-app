"""
Quick-start development settings - unsuitable for production
See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/
"""
from datetime import datetime, timedelta
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SECRET_KEY = '00aqmqedb05688z06d_%m%a==yu10am82ff)rcxk4il6@6%2=$'
DEBUG = True
ALLOWED_HOSTS = ['*']
APPEND_SLASH = False

# Application definition

ASGI_APPLICATION = 'racetime.routing.application'

INSTALLED_APPS = [
    'racetime',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.humanize',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'debug_toolbar',
    'captcha',
    'channels',
    'corsheaders',
    'django.forms',
    'django_admin_listfilter_dropdown',
    'oauth2_provider',
    'rest_framework'
]

MIDDLEWARE = [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'oauth2_provider.middleware.OAuth2TokenMiddleware',
]

ROOT_URLCONF = 'project.urls'

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
                'racetime.apps.context_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'project.wsgi.application'

FORM_RENDERER = 'django.forms.renderers.TemplatesSetting'

SILENCED_SYSTEM_CHECKS = ['captcha.recaptcha_test_key_error']

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'racetime.utils.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('racetime.redis', 6379)],
        },
    },
}

CORS_ORIGIN_ALLOW_ALL = True
REAL_IP_HEADER = None

INTERNAL_IPS = ['127.0.0.1']
DEBUG_TOOLBAR_CONFIG = {
    'DISABLE_PANELS': {'debug_toolbar.panels.redirects.RedirectsPanel'},
    'SHOW_TOOLBAR_CALLBACK': 'project.debug.show_toolbar',
}

# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'racetime',
        'USER': 'racetime',
        'PASSWORD': 'racetime',
        'HOST': 'racetime.db',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    },
}

# Authentication

AUTHENTICATION_BACKENDS = (
    'oauth2_provider.backends.OAuth2Backend',
    'django.contrib.auth.backends.ModelBackend',
)
AUTH_USER_MODEL = 'racetime.User'
LOGIN_URL = '/account/auth'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-gb'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'node_modules', 'jquery', 'dist'),
    os.path.join(BASE_DIR, 'node_modules', 'jquery-form', 'dist'),
    os.path.join(BASE_DIR, 'node_modules', 'jquery-ui-dist'),
    os.path.join(BASE_DIR, 'node_modules', 'js-cookie', 'src'),
]
STATIC_URL = '/static/'

# Media files

MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Logging

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'django.server': {
            '()': 'django.utils.log.ServerFormatter',
            'format': '[{server_time}] {message}',
            'style': '{',
        }
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
        'django.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'django.server',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'django.server': {
            'handlers': ['django.server'],
            'level': 'WARNING',
            'propagate': False,
        },
        'racebot': {
            'handlers': ['django.server'],
            'level': 'INFO',
            'propagate': False,
        },
    }
}

# OAuth2 settings

OAUTH2_PROVIDER = {
    'AUTHORIZATION_CODE_EXPIRE_SECONDS': 600,
    'SCOPES': {
        'read': 'See your name, Twitch username and basic user information.',
        'chat_message': 'Send chat messages to race rooms on your behalf.',
        'race_action': 'Join and interact with races on your behalf.',
        'create_race': 'Create race rooms on your behalf.',
    },
}

# Site details

EMAIL_FROM = 'hello@racetime.dev'

RT_SITE_URI = 'http://localhost:8000'

RT_SITE_INFO = {
    'title': 'racetime.dev',
    'header_text': 'racetime<span class="dot">.</span>dev',
    'meta_site_name': 'racetime.dev',
    'meta_description': 'racetime development environment',
    'footer_text': ['Development environment. Last restart: ' + datetime.now().isoformat()],
    'footer_links': (
        (
            {'text': 'Discord', 'link': 'https://discord.racetime.gg', 'img': 'racetime/image/social/discord.svg'},
            {'text': 'GitHub', 'link': 'https://github.com/racetimeGG/racetime-app', 'img': 'racetime/image/social/github.svg'},
        ),
    ),
    'extra_scripts': [],
}

RT_CACHE_TIMEOUT = {
    'RaceListData': 30,
    'CategoryData': 60,
    'RaceData': 5,
    'RaceRenders': 15,
}

REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}
