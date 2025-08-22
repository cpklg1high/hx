from django.urls import re_path
from .views import (
    TermListCreate, RoomList, SubjectList, TeacherList,
    ClassGroupListCreate, ClassGroupEnroll, ClassGroupUnenroll,
    LessonsView, LessonLeaveView, AttendanceCommitView, AttendanceRevertView
)

urlpatterns = [
    # 基础字典 & 学期
    re_path(r'^terms/?$', TermListCreate.as_view()),
    re_path(r'^rooms/?$', RoomList.as_view()),
    re_path(r'^subjects/?$', SubjectList.as_view()),
    re_path(r'^teachers/?$', TeacherList.as_view()),

    # 班级
    re_path(r'^class-groups/?$', ClassGroupListCreate.as_view()),
    re_path(r'^class-groups/(?P<pk>\d+)/enroll/?$', ClassGroupEnroll.as_view()),
    re_path(r'^class-groups/(?P<pk>\d+)/unenroll/?$', ClassGroupUnenroll.as_view()),

    # 课表
    re_path(r'^lessons/?$', LessonsView.as_view()),

    # 请假（课前）
    re_path(r'^lessons/(?P<pk>\d+)/leave/?$', LessonLeaveView.as_view()),

    # 签到/消课（课后）
    re_path(r'^lessons/(?P<pk>\d+)/attendance/?$', AttendanceCommitView.as_view()),
    re_path(r'^lessons/(?P<pk>\d+)/attendance/revert/?$', AttendanceRevertView.as_view()),
]
