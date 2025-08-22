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
