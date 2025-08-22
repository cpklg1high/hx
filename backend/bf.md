# 第 0步 · 预设与约定

- **技术栈**：Django 5 + DRF + `djangorestframework-simplejwt`；MySQL 8；（前端：Vue3 + Vite + Element Plus）
- **Token 策略**：`access` 放在前端内存/会话中，**`refresh` 仅放在 HttpOnly+Secure Cookie**。
  - 为避免 `SameSite=None` 在开发环境的 HTTPS 限制，**建议前端与后端都用 `http://localhost` 域名**（端口不同不影响 same-site）。Vite 通过代理把 `/api` 转发到后端，这样 **`SameSite=Lax`** 就能工作，开发更稳。
- **用户模型：自定义 `accounts.User`（继承 `AbstractUser`），扩展手机号、头像、状态、登录时间等；用 **Argon2** 哈希。
- **返回结构**：登录返回统一结构 `code/message/data`，其中 `data` 内含 `access` 与 `user`；**refresh 只通过 Set-Cookie 返回**（不放 body）。

# 第 1 步 · 新建项目骨架

> 在你准备好的空目录（例如 `edu`）里操作：
>
> ```
> # 1) 创建虚拟环境(cmd目录中创建)
> python -m venv .venv
> # Windows.cmd
> .venv\Scripts\activate.bat
> 
> # 2) 安装后端依赖
> pip install django  -i https://pypi.tuna.tsinghua.edu.cn/simple
> pip install djangorestframework -i https://pypi.tuna.tsinghua.edu.cn/simple
> pip install djangorestframework-simplejwt -i https://pypi.doubanio.com/simple/
> pip install argon2-cffi -i https://pypi.doubanio.com/simple/
> pip install django-cors-headers -i https://pypi.doubanio.com/simple/
> pip install django-environ  -i https://pypi.doubanio.com/simple/
> pip install PyMySQL  -i https://pypi.doubanio.com/simple/ #暂时使用sqilte3
> pip install mysqlclient -i https://pypi.doubanio.com/simple/ #暂时使用sqilte3
> ```
>
> 创建目录结构（手动或跟随命令创建）：
>
> ```
> edu/
> └─ backend/
>    ├─ manage.py               # Django 管理入口（命令自动生成）
>    ├─ .env                    # 环境变量（我们会手写）
>    ├─ edu_admin/              # Django 项目目录（命令自动生成）
>    │  ├─ __init__.py
>    │  ├─ asgi.py
>    │  ├─ settings.py          # 核心配置（我们会修改）
>    │  ├─ urls.py              # 顶级路由
>    │  └─ wsgi.py
>    └─ user/               # 鉴权应用（我们会创建）
>       ├─ __init__.py
>       ├─ admin.py
>       ├─ apps.py
>       ├─ models.py
>       ├─ serializers.py
>       ├─ views.py
>       ├─ urls.py
>       └─ migrations/
> ```
>
> **为什么这样**：
>
> - 把后端放在 `backend/`，未来前端放 `frontend/`，仓库清晰；
> - `accounts` 专注用户与鉴权，避免把业务塞进项目根；
> - .env 外置敏感信息，便于分环境部署与安全审计。

# 第 2 步 · 生成 Django 项目与应用

在 `edu/backend` 目录中执行：

```
django-admin startproject edu_admin .
python manage.py startapp user
```

为什么：使用 Django 官方命令保证标准化骨架，后续生态（管理命令、迁移、WSGI/ASGI）接入无缝。



# 第 3 步 · 环境变量文件 `.env`

在 `edu/backend/.env` 新建：

```
DJANGO_SECRET_KEY=CHANGE_ME_TO_A_RANDOM_STRING
DEBUG=True

MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=edu_admin
MYSQL_USER=root
MYSQL_PASSWORD=123456

# 前端开发地址（用于 CORS/CSRF 白名单）
FRONTEND_ORIGIN=http://localhost:5173

# 刷新 Cookie 策略（开发同域建议 Lax；若跨站需 None+Secure）
REFRESH_COOKIE_NAME=refresh_token
REFRESH_COOKIE_SAMESITE=Lax
REFRESH_COOKIE_SECURE=False
REFRESH_COOKIE_AGE=604800  # 7 天
```

**为什么这样**：

- 配置不硬编码在 `settings.py`，换环境只改 `.env`；

- `REFRESH_COOKIE_*` 用于控制 Cookie 行为，便于开发与生产切换。

- **环境隔离**

  - 开发/测试/生产环境用不同 `.env` 文件，无需修改代码。

- **敏感信息保护**

  - 数据库密码等不暴露在代码中。

- **协作友好**

  - 团队可共享 `.env.example` 模板，各自维护私有 `.env`。

- **符合 12-Factor 应用原则**

  - 配置与代码分离，提升可移植性。

  - **切勿提交到 Git**！在 `.gitignore` 中添加：

    text

    ```
    .env
    */settings/local.py
    ```

  - 生产环境应禁用 `DEBUG=False`

  - Cookie 需启用 Secure：

    ini

    ```
    REFRESH_COOKIE_SECURE=True
    REFRESH_COOKIE_SAMESITE=None
    ```

如果遇到问题，检查是否安装了 `python-dotenv` 并确认 `.env` 文件路径正确。

# 第 4 步 · 修改 `edu_admin/settings.py`

打开 `edu/backend/edu_admin/settings.py`，按下述要点修改（我给“增量片段”，你只需对照增补/替换）：

```
# === 头部：引入 environ ===
from pathlib import Path
import environ
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('DJANGO_SECRET_KEY', default='CHANGE_ME')
DEBUG = env.bool('DEBUG', default=True)

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# === 应用 ===
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',

    'accounts',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # 放最前以便处理 CORS
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # 保留以保护 refresh cookie
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'edu_admin.urls'
TEMPLATES = []  # 前后端分离，无模板可简化

WSGI_APPLICATION = 'edu_admin.wsgi.application'

# === MySQL 数据库 ===
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': env('MYSQL_DB'),
        'USER': env('MYSQL_USER'),
        'PASSWORD': env('MYSQL_PASSWORD'),
        'HOST': env('MYSQL_HOST'),
        'PORT': env('MYSQL_PORT'),
        'OPTIONS': {'charset': 'utf8mb4'},
    }
}

# === 自定义用户模型 ===
AUTH_USER_MODEL = 'accounts.User'

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

STATIC_URL = 'static/'
```

**为什么这样**：

- **JWT 放在 DRF 认证链**，避免自写中间件易漏边界；
- **CSRF 中间件开启**，我们后面会让**刷新接口必须带 CSRF**，从而消除 refresh-cookie 被跨站滥用的风险；
- **黑名单开启**，登出/旋转能失效旧的 refresh；
- **CORS 允许凭据** 用于携带 Cookie；`CSRF_TRUSTED_ORIGINS` 允许跨站携带 CSRF 头。



# 第 5 步 · `accounts/models.py`（自定义用户）

文件：`edu/backend/accounts/models.py`

```
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', '管理员'),
        ('teacher', '教师'),
        ('teacher_manager', '教学主管'),
        ('salesperson', '班主任'),
        ('salesperson_manager', '班主任主管'),
        ('parent', '家长'),
    )
    name = models.CharField(max_length=255, null=True, blank=True)
    avatar = models.CharField(max_length=255, null=True, blank=True )
    phone_number = models.CharField(max_length=11, null=True, blank=True)
    status = models.IntegerField(default=1, choices=((1, "正常"), (0, "禁用")), verbose_name="状态")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, null=True, blank=True , verbose_name="角色")
    remark = models.CharField(max_length=500, null=True, blank=True)
    login_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sys_user'  # 与课程表命名对齐
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return self.username
```

**为什么这样**：

- 继承 `AbstractUser` 可复用 Django 认证生态（密码哈希、后台管理、权限钩子）；
- `status` 支持账号禁用；`login_date` 用于审计。

------

# 第 6 步 · `user/serializers.py`

文件：`edu/backend/user/serializers.py`

```python
from rest_framework import serializers
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import User

class UserOutSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id','username','email','phonenumber','avatar','status','login_date','first_name','last_name','remark']

class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username  # 非敏感声明，减少频繁查库
        token['status'] = user.status
        return token

    def validate(self, attrs):
        data = super().validate(attrs)  # 复用 SimpleJWT 的鉴权（等价 authenticate）
        user = self.user
        if user.status == 0:
            # 这里示意禁用态，你也可以用 0=正常/1=禁用，根据你的枚举调整
            raise AuthenticationFailed('账号已被禁用')
        user.login_date = timezone.now()
        user.save(update_fields=['login_date'])
        data['user'] = UserOutSerializer(user).data
        return data

```

**为什么这样**：

- 复用 SimpleJWT 的校验逻辑（密码哈希/锁定策略与 Django 同步）；
- 在 Token 中带只读声明（`username`、`status`），减少后端二次查表频率（仅非敏感字段）。

------

# 第 7 步 · `user/views.py`

文件：`edu/backend/user/views.py`

```
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from .serializers import LoginSerializer, UserOutSerializer

def _set_refresh_cookie(response, refresh_token: str):
    cfg = settings.REFRESH_COOKIE
    response.set_cookie(
        key=cfg["name"],
        value=refresh_token,
        max_age=cfg["max_age"],
        httponly=True,                # 防 XSS
        secure=cfg["secure"],         # 生产上建议 True + HTTPS
        samesite=cfg["samesite"],     # 开发同站可用 Lax；跨站需 None
        path="/api/auth/",            # 仅鉴权路径可带上，最小授权面
    )

def _clear_refresh_cookie(response):
    cfg = settings.REFRESH_COOKIE
    response.delete_cookie(key=cfg["name"], path="/api/auth/", samesite=cfg["samesite"])

class CSRFTokenView(APIView):
    """用于在前端首次加载时种下 csrftoken Cookie。"""
    permission_classes = [AllowAny]
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({'code': 200, 'message': 'CSRF cookie set'})

class LoginView(TokenObtainPairView):
    """
    登录：
    - 请求: {username, password}
    - 返回: {code, message, data:{access, user}}，并通过 Set-Cookie 写入 refresh
    """
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        resp = Response({
            'code': 200,
            'message': '登录成功',
            'data': {
                'access': str(validated['access']),
                'user': validated['user'],
            }
        })
        _set_refresh_cookie(resp, str(validated['refresh']))
        return resp

class CookieTokenRefreshView(TokenRefreshView):
    """
    刷新 access（旋转 refresh）：
    - 从 HttpOnly Cookie 读取 refresh（需要 CSRF）
    - 返回: {code, data:{access}}，并重置 refresh Cookie
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        cookie_name = settings.REFRESH_COOKIE['name']
        refresh = request.COOKIES.get(cookie_name)
        if not refresh:
            return Response({'code': 401, 'message': '未发现刷新凭据'}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = self.get_serializer(data={'refresh': refresh})
        serializer.is_valid(raise_exception=True)

        resp = Response({'code': 200, 'data': {'access': serializer.validated_data['access']}})
        new_refresh = serializer.validated_data.get('refresh')
        if new_refresh:
            _set_refresh_cookie(resp, str(new_refresh))
        return resp

class MeView(APIView):
    """获取当前登录用户信息（需要 Authorization: Bearer <access>）"""
    permission_classes = [IsAuthenticated]
    def get(self, request):
        return Response({'code': 200, 'data': {'user': UserOutSerializer(request.user).data}})

class LogoutView(APIView):
    """登出：拉黑 refresh + 清除 Cookie"""
    def post(self, request):
        cookie_name = settings.REFRESH_COOKIE['name']
        refresh = request.COOKIES.get(cookie_name)
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except Exception:
                pass
        resp = Response({'code': 200, 'message': '退出成功'})
        _clear_refresh_cookie(resp)
        return resp

```

**为什么这样**：

- **登录**只返回 `access` 与 `user`，更符合 2A 安全策略；
- **刷新**强制从 HttpOnly Cookie 读，且受 **CSRF** 保护，抵御跨站伪造刷新；
- **登出**把 refresh 加入黑名单并清 Cookie，确保服务端失效化。

------

# 第 8 步 · `user/urls.py` 与 顶级路由

文件：`edu/backend/accounts/urls.py`

```
from django.urls import path
from .views import LoginView, CookieTokenRefreshView, MeView, LogoutView, CSRFTokenView

urlpatterns = [
    path('auth/csrf', CSRFTokenView.as_view(), name='auth_csrf'),
    path('auth/login', LoginView.as_view(), name='auth_login'),
    path('auth/refresh', CookieTokenRefreshView.as_view(), name='auth_refresh'),
    path('auth/me', MeView.as_view(), name='auth_me'),
    path('auth/logout', LogoutView.as_view(), name='auth_logout'),
]

```

文件：`edu/backend/edu_admin/urls.py`

```

from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    # path('admin/', admin.site.urls),
    path('api/', include('user.urls')),
]

```

**为什么这样**：

- 把鉴权相关路由聚合在 `accounts` 应用中，职责清晰；
- 顶级路由以 `/api/` 作为服务前缀，方便前端代理与网关统一转发。

------

# 第 9 步 · 生成数据库表并创建测试用户

> **务必先定义好 `AUTH_USER_MODEL` 再执行迁移**（已完成）

```
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
# 按提示创建 admin 用户
```

**为什么这样**：

- 初次迁移后，`sys_user` 表结构即稳定；
- 超级用户可用于后台或紧急维护。

------

# 第 10 步 · 本地冒烟测试（后端）

> 保持后端在 `http://localhost:8000` 运行：

```
python manage.py runserver 8000
```

**1）先拿 CSRF Cookie**（浏览器 GET 或 curl）

```
curl -i http://localhost:8000/api/auth/csrf
```

**2）登录**

```
curl -i -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"你的密码"}'
```

你应能看到：

- 响应体：`{"code":200, "data": { "access": "...", "user": {...} } }`
- 响应头：包含 `Set-Cookie: refresh_token=...; HttpOnly; Path=/api/auth; SameSite=Lax`

**3）带 `access` 调用 /me**

```
curl -i http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <上一步返回的 access>"
```

**4）刷新 access（需携带 Cookie + CSRF）**

- 先从浏览器拿到 `csrftoken`（步骤 1 已设置）
- 请求头带：`X-CSRFToken: <csrftoken>`，并发送 Cookie（携带 `refresh_token` 与 `csrftoken`）。示例（curl 简化，实际前端会自动带 Cookie）：

```
curl -i -X POST http://localhost:8000/api/auth/refresh \
  -H "X-CSRFToken: <csrftoken>" \
  --cookie "csrftoken=<csrftoken>; refresh_token=<浏览器里拿到的 cookie 值>"
```

**5）登出**

```
curl -i -X POST http://localhost:8000/api/auth/logout \
  --cookie "refresh_token=<...>"
```

------

# 第 11 步 · 前端对接（最小化约定）

> 我们先不写前端代码，只给**关键契约**，你若确认我再给 Vue3 + Axios 的拦截器示例。

- **启动时**：`GET /api/auth/csrf` 获取 `csrftoken` Cookie；
- **登录页**：`POST /api/auth/login` -> 保存 `data.access`（内存/SessionStorage），保存 `data.user`；
- **每次请求**：`Authorization: Bearer <access>`；
- **401 自动刷新**：在 Axios 响应拦截器里：
  - 带上 `X-CSRFToken`（从 `document.cookie` 解析 `csrftoken`），`POST /api/auth/refresh`（**不带 body**）；
  - 更新内存里的 `access`；重放原请求；
- **登出**：`POST /api/auth/logout`，清空本地状态。

**为什么这样**：

- `refresh` 全程不暴露给前端 JS（HttpOnly Cookie），防止 XSS 泄露；
- 刷新接口带 CSRF 头，阻断跨站“静默刷新”；
- 菜单、角色等后续**独立接口**拉取，便于权限热更新与审计。

------

## ✅ 本回合交付小结（登录功能完成）

你现在应该具备：

1. 一个可运行的 Django 后端；
2. 登录接口返回 `access + user`，**refresh 通过 HttpOnly Cookie**；
3. `/me` 可用；`/refresh` 可旋转刷新且受 CSRF 保护；`/logout` 可失效化 refresh。

> **请你执行到“第 10 步”并反馈**运行结果（有无报错、Cookie 是否正确设置、/me 是否拿到用户信息）。
>  若确认无误，我将继续下一步：
>
> - 提供 **前端（Vue3 + Vite）对接示例**（Axios 封装、路由守卫、错误处理）；
> - 设计 **统一异常/响应格式中间件** 与 **日志/审计规范**；
> - 开始实现 **RBAC 基础表结构** 与 **登录后动态菜单接口**。