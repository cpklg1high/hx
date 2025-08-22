from django.urls import path
from .views import DevEnrollmentCreateView

urlpatterns = [
    path('dev/enrollments/create', DevEnrollmentCreateView.as_view()),
]
