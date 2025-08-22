from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DictGradesView, DictRelationsView, DictVisitChannelsView,
    SalespersonsView, StudentsSearchView, SchoolsView,
    StudentViewSet, ReferralRewardByStudentView
)

router = DefaultRouter()
router.register(r'students', StudentViewSet, basename='students')

urlpatterns = [
    path('dicts/grades', DictGradesView.as_view()),
    path('dicts/relations', DictRelationsView.as_view()),
    path('dicts/visit_channels', DictVisitChannelsView.as_view()),
    path('users/salespersons', SalespersonsView.as_view()),
    path('students/search', StudentsSearchView.as_view()),
    # 学校列表（按拼音排序 + 搜索）
    path('schools', SchoolsView.as_view()),
    # 奖励查询（之前加过）
    path('referral/reward-by-student/<int:student_id>', ReferralRewardByStudentView.as_view()),
    path('', include(router.urls)),
]
