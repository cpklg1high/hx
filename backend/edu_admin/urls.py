
from django.contrib import admin
from django.urls import path,include

urlpatterns = [
    # path('admin/', admin.site.urls),
    path('api/', include('user.urls')),
    path('api/',include('students.urls')),
    path('api/', include('academics.urls')),
    path('api/', include('billing.urls')),
    path('api/schedule/', include('schedule.urls')),
]
