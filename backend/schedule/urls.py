from django.urls import re_path
from .views import (
    TermListCreate, RoomList, SubjectList, TeacherList,
    ClassGroupListCreate, ClassGroupEnroll, ClassGroupUnenroll,
    LessonsView, LessonLeaveView, AttendanceCommitView, AttendanceRevertView,
    # 新增导入
    LessonParticipantViewSet
)

from .views_cycle import (
    CampusListView,
    CycleListCreateView, CycleDetailView,
    CycleBoardView,
    CycleRosterView,
    CyclePublishView,
    CycleMasterRosterView,PreplanSlotListCreateView,
    PreplanSlotDetailView
)

# 新增：把 ViewSet 映射为函数视图（保持与你其它 re_path 风格一致）
participant_list = LessonParticipantViewSet.as_view({'get': 'list', 'post': 'create'})
participant_detail = LessonParticipantViewSet.as_view({'delete': 'destroy'})

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

    # ========= 新增：试听 / 临时排课一次 =========
    # 列表 + 批量创建
    re_path(r'^lessons/(?P<lesson_id>\d+)/participants/?$', participant_list, name='lessonparticipant-list'),
    # 删除单个参与者
    re_path(r'^lessons/(?P<lesson_id>\d+)/participants/(?P<pk>\d+)/?$', participant_detail, name='lessonparticipant-detail'),

    re_path(r'^cycle-schedule/campuses/?$', CampusListView.as_view()),
    re_path(r'^cycle-schedule/cycles/?$', CycleListCreateView.as_view()),
    re_path(r'^cycle-schedule/cycles/(?P<pk>\d+)/?$', CycleDetailView.as_view()),
    re_path(r'^cycle-schedule/cycles/(?P<pk>\d+)/board/?$', CycleBoardView.as_view()),
    re_path(r'^cycle-schedule/cycles/(?P<cycle_id>\d+)/class-groups/(?P<class_group_id>\d+)/roster/?$',
            CycleRosterView.as_view()),
    re_path(r'^cycle-schedule/cycles/(?P<pk>\d+)/publish/?$', CyclePublishView.as_view()),
    re_path(r'^cycle-schedule/cycles/(?P<cycle_id>\d+)/roster/?$', CycleMasterRosterView.as_view()),
    re_path(r'^cycle-schedule/preplan/slots/?$', PreplanSlotListCreateView.as_view()),
    re_path(r'^cycle-schedule/preplan/slots/(?P<pk>\d+)/?$', PreplanSlotDetailView.as_view()),

]
