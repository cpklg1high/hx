from pathlib import Path
import environ
from datetime import timedelta


# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')


SECRET_KEY = env('DJANGO_SECRET_KEY', default='CHANGE_ME')
DEBUG = env.bool('DEBUG', default=True)

ALLOWED_HOSTS = ['localhost', '127.0.0.1']


INSTALLED_APPS = [
    # 'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',

    'user',
    'academics',
    'students',

    'billing',

    'schedule',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'edu_admin.urls'

WSGI_APPLICATION = 'edu_admin.wsgi.application'


TEMPLATES = []  # 前后端分离，无模板可简化
# TEMPLATES = [
#     {
#         'BACKEND': 'django.template.backends.django.DjangoTemplates',
#         'DIRS': [],
#         'APP_DIRS': True,
#         'OPTIONS': {
#             'context_processors': [
#                 'django.template.context_processors.debug',
#                 'django.template.context_processors.request',
#                 'django.contrib.auth.context_processors.auth',
#                 'django.contrib.messages.context_processors.messages',
#             ],
#         },
#     },
# ]


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',  # 改为内置sqlite引擎
        'NAME': BASE_DIR / 'db.sqlite3',         # 数据文件放在项目根目录
    }
}

# === 自定义用户模型 ===
AUTH_USER_MODEL = 'user.User'
# AUTH_PASSWORD_VALIDATORS = [
#     {
#         'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
#     },
#     {
#         'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
#     },
# ]

# === 密码哈希：Argon2 优先 ===
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
]

# === DRF 配置 ===
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.AllowAny',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '10/min',
        'user': '60/min',
    },
    'UNAUTHENTICATED_USER': None,  # 避免匿名用户混淆
}


# === SimpleJWT ===
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,            # 刷新即旋转 refresh
    'BLACKLIST_AFTER_ROTATION': True,         # 旧 refresh 进入黑名单
    'AUTH_HEADER_TYPES': ('Bearer',),
    'SIGNING_KEY': SECRET_KEY,
    'ALGORITHM': 'HS256',
}

# === CORS/CSRF ===
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [
    # 你也可以用 CORS_ALLOWED_ORIGINS = [env('FRONTEND_ORIGIN')]
    r"^http://localhost(:\d+)?$",
]
CSRF_TRUSTED_ORIGINS = [env('FRONTEND_ORIGIN')]

# CSRF Cookie 需可被前端读取以携带到 Header
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_NAME = "csrftoken"


# === 刷新 Cookie 策略（从 .env 读取）===
REFRESH_COOKIE = {
    "name": env('REFRESH_COOKIE_NAME', default='refresh_token'),
    "samesite": env('REFRESH_COOKIE_SAMESITE', default='Lax'),  # Lax/Strict/None
    "secure": env.bool('REFRESH_COOKIE_SECURE', default=False),
    "max_age": env.int('REFRESH_COOKIE_AGE', default=60*60*24*7),  # 7天
}

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
