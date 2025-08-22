from django.urls import path
from .views import LoginView, CookieTokenRefreshView, MeView, LogoutView, CSRFTokenView

urlpatterns = [
    path('auth/csrf', CSRFTokenView.as_view(), name='auth_csrf'),
    path('auth/login', LoginView.as_view(), name='auth_login'),
    path('auth/refresh', CookieTokenRefreshView.as_view(), name='auth_refresh'),
    path('auth/me', MeView.as_view(), name='auth_me'),
    path('auth/logout', LogoutView.as_view(), name='auth_logout'),
]
