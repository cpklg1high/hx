# backend/schedule/models.py
from decimal import Decimal
import json

from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings

from students.models import Student, GRADE_CHOICES  # 年级枚举与学生
# 避免潜在循环导入，如需使用 Enrollment，请在使用处延迟导入
# from academics.models import Enrollment

User = get_user_model()

# ================== SQLite 兼容：JSONTextField ==================
class JSONTextField(models.TextField):
    """
    在 SQLite 上用 TextField 存 JSON 字符串：
    - 读取自动 json.loads -> dict/list
    - 写入可直接给 dict/list，自动 json.dumps
    - 允许 None/'' -> {}
    """
    def from_db_value(self, value, expression, connection):
        if value in (None, ''):
            return {}
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return {}

    def to_python(self, value):
        if value in (None, ''):
            return {}
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return {}

    def get_prep_value(self, value):
        if value in (None, ''):
            return '{}'
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        # 已是字符串，尽力校验
        try:
            json.loads(value)
            return value
        except Exception:
            return json.dumps(str(value), ensure_ascii=False)


# ================== 基础枚举 ==================
COURSE_MODE = (
    ('one_to_one', '一对一'),
    ('one_to_two', '一对二'),  # 实际容量 <= 4（默认2），1v2/1v3/1v4 用 capacity 表达
    ('small_class', '小班'),   # 无上限（capacity 可空）
)

DEDUCT_UNIT = (
    ('hours', '小时'),
    ('sessions', '节'),
)

TERM_TYPE = (
    ('spring', '春季'),
    ('summer', '暑假'),
    ('autumn', '秋季'),
    ('winter', '寒假'),
)

LESSON_STATUS = (
    ('scheduled', '已排课'),
    ('finished', '已完成'),
    ('canceled', '已取消'),
)

ATTEND_STATUS = (
    ('present', '签到'),          # 扣课
    ('leave', '请假'),            # 课前设定，不扣
    ('absent', '缺席'),           # 未请假且未到，不扣，仅记录
)

WORKLOG_STATUS = (
    ('pending', '待结算'),
    ('paid', '已结算'),
)

PHASE = (  # 科目学段：primary=小学，junior=初中，senior=高中
    ('primary', '小学'),
    ('junior', '初中'),
    ('senior', '高中'),
)

# ================== 新增：校区 ==================
class Campus(models.Model):
    """校区（Room 归属到 Campus；周期、课表按校区过滤）"""
    name = models.CharField(max_length=50, unique=True)
    code = models.CharField(max_length=20, blank=True, default='')
    address = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'edu_campus'
        ordering = ['name']

    def __str__(self):
        return self.name


class Term(models.Model):
    """学期/季度：限制排课时间边界"""
    name = models.CharField(max_length=50)                # 例：2025暑假班
    type = models.CharField(max_length=10, choices=TERM_TYPE)
    year = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    remark = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        db_table = 'edu_term'
        ordering = ['-year', 'start_date']
        indexes = [models.Index(fields=['year', 'type', 'is_active'])]

    def __str__(self):
        return f'{self.name}({self.start_date}~{self.end_date})'


class Room(models.Model):
    """教室"""
    name = models.CharField(max_length=50, unique=True)
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)  # None 代表不限制
    location = models.CharField(max_length=100, blank=True, default='')

    # 归属校区（兼容历史，可空；迁移后请补齐）
    campus = models.ForeignKey(Campus, on_delete=models.PROTECT, related_name='rooms', null=True, blank=True)

    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'edu_room'
        ordering = ['name']

    def __str__(self):
        return self.name


class Subject(models.Model):
    """科目"""
    name = models.CharField(max_length=50, unique=True)   # 数学/语文/英语…
    phase = models.CharField(max_length=10, choices=PHASE, default='junior')

    class Meta:
        db_table = 'edu_subject'
        ordering = ['name']

    def __str__(self):
        return self.name


class ClassGroup(models.Model):
    """
    班级（承载规则与成员）
    容量策略：
      - one_to_one: 固定 1
      - one_to_two: <=4（默认 2）
      - small_class: 不限制（capacity 可空）
    """
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='classes')
    course_mode = models.CharField(max_length=20, choices=COURSE_MODE, db_index=True)
    grade = models.PositiveSmallIntegerField(choices=GRADE_CHOICES, db_index=True)
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT, related_name='classes')
    room_default = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='classes', null=True, blank=True)
    teacher_main = models.ForeignKey(User, on_delete=models.PROTECT, related_name='teaching_classes')

    name = models.CharField(max_length=80, blank=True, default='')  # 可选命名：如“初二数学1班”
    capacity = models.PositiveSmallIntegerField(null=True, blank=True)  # 见容量策略
    status = models.CharField(max_length=10, default='active')  # active/archived
    remark = models.CharField(max_length=200, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_class_group'
        ordering = ['-id']
        indexes = [models.Index(fields=['term', 'grade', 'course_mode'])]

    def __str__(self):
        return f'ClassGroup<{self.id}> {self.name or ""}'


class ScheduleRule(models.Model):
    """
    排课规则
    - weekly: 周循环
        * weekly_days_mask: 位掩码表示周几（bit0=周一 ... bit6=周日）
        * weekly_start_time
        * weekly_duration（分钟）
    - custom: 自定义多段（见下方 ScheduleCustomEntry 子表）
    保存后据 Term 边界生成 Lesson。
    """
    RULE_TYPE = (('weekly', 'weekly'), ('custom', 'custom'))

    class_group = models.ForeignKey(ClassGroup, on_delete=models.CASCADE, related_name='rules')
    type = models.CharField(max_length=10, choices=RULE_TYPE)

    # weekly
    weekly_days_mask = models.PositiveSmallIntegerField(null=True, blank=True)  # 0~127
    weekly_start_time = models.TimeField(null=True, blank=True)
    weekly_duration = models.PositiveIntegerField(null=True, blank=True)  # 分钟，例：小班默认 100

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_schedule_rule'
        ordering = ['-id']


class ScheduleCustomEntry(models.Model):
    """
    自定义多段规则的单条记录（避免 JSONField）
    例：2025-07-01 18:00 持续 100 分钟
    """
    rule = models.ForeignKey(ScheduleRule, on_delete=models.CASCADE, related_name='custom_entries')
    date = models.DateField()
    start_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()

    class Meta:
        db_table = 'edu_schedule_custom_entry'
        ordering = ['date', 'start_time']
        indexes = [models.Index(fields=['rule', 'date'])]


class Lesson(models.Model):
    """课次（可覆盖班级默认教室/老师）"""
    class_group = models.ForeignKey(ClassGroup, on_delete=models.PROTECT, related_name='lessons')
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()

    room = models.ForeignKey(Room, on_delete=models.PROTECT, related_name='lessons', null=True, blank=True)
    teacher = models.ForeignKey(User, on_delete=models.PROTECT, related_name='lessons', null=True, blank=True)

    status = models.CharField(max_length=10, choices=LESSON_STATUS, default='scheduled')
    lock_attendance = models.BooleanField(default=False)  # 提交后锁定签到

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_lesson'
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['date', 'start_time']),
            models.Index(fields=['class_group', 'date']),
        ]

    def __str__(self):
        return f'Lesson<{self.id}> {self.date} {self.start_time}-{self.end_time}'


class ClassEnrollment(models.Model):
    """学生加入班级的关系（可多次进出；限制“同一时间仅1个有效记录”）"""
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='class_enrollments')
    class_group = models.ForeignKey(ClassGroup, on_delete=models.PROTECT, related_name='student_enrollments')
    joined_at = models.DateTimeField(default=timezone.now)
    left_at = models.DateTimeField(null=True, blank=True)
    is_trial = models.BooleanField(default=False)  # 试听预留

    class Meta:
        db_table = 'edu_class_enrollment'
        ordering = ['-id']
        constraints = [
            # 注意：SQLite 对“带 condition 的唯一约束”不强制，但 Django 保持声明以利于未来迁移到 PG/MySQL
            models.UniqueConstraint(
                fields=['student', 'class_group'],
                condition=models.Q(left_at__isnull=True),
                name='uniq_active_class_enrollment'
            ),
        ]


class LessonLeave(models.Model):
    """
    课前请假（仅用于标记“请假”状态；课后不可撤销）
    - 由 admin 或 学生班主任 设置
    - 一键请假 = 批量创建该 Lesson 的多条 leave 记录
    """
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='leaves')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='lesson_leaves')
    reason = models.CharField(max_length=200, blank=True, default='')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_lesson_leave'
        unique_together = ('lesson', 'student')
        ordering = ['-id']


class Attendance(models.Model):
    """
    出勤/消课记录（课后提交）
    - present: 扣课（先付费再赠送）
    - leave/absent: 不扣，仅记录
    """
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='attendances')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='attendances')
    status = models.CharField(max_length=10, choices=ATTEND_STATUS)  # present/leave/absent

    # 扣课明细（仅 present 才会填写）
    deduct_unit = models.CharField(max_length=10, choices=DEDUCT_UNIT, null=True, blank=True)
    deduct_qty = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    deduct_from = models.CharField(max_length=10, null=True, blank=True)  # paid/gift（主来源）
    paid_used = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, default=None)
    gift_used = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True, default=None)

    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_attendance'
        ordering = ['-id']
        unique_together = ('lesson', 'student')


class TeacherWorklog(models.Model):
    """教师工时（由签到生成；工资模块独立结算）"""
    lesson = models.ForeignKey(Lesson, on_delete=models.PROTECT, related_name='worklogs')
    teacher = models.ForeignKey(User, on_delete=models.PROTECT, related_name='worklogs')
    work_hours = models.DecimalField(max_digits=5, decimal_places=2)  # 小班=2.00，其它按时长(四舍五入到0.5)
    rule_code = models.CharField(max_length=50, default='normal')    # small_class_x2 / normal
    status = models.CharField(max_length=10, choices=WORKLOG_STATUS, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_teacher_worklog'
        ordering = ['-id']
        indexes = [models.Index(fields=['teacher', 'status'])]


class LessonParticipant(models.Model):
    """
    课次临时/试听参与者：
      - trial 试听（不扣课）
      - temp  正常排课（周期发布或“临时一次”均可用此类型）
    """
    TYPE_TRIAL = 'trial'   # 试听（不扣课）
    TYPE_TEMP = 'temp'     # 正常排课或临时一次（按正常扣课）
    TYPE_CHOICES = (
        (TYPE_TRIAL, 'Trial'),
        (TYPE_TEMP, 'Temporary'),
    )

    lesson = models.ForeignKey('schedule.Lesson', on_delete=models.CASCADE, related_name='participants')
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='lesson_participations')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('lesson', 'student')
        indexes = [
            models.Index(fields=['lesson', 'student']),
            models.Index(fields=['type']),
        ]

    def __str__(self):
        return f'{self.lesson_id}-{self.student_id}-{self.type}'


# ================== 新增：排课周期层（与既有逻辑解耦） ==================
class Cycle(models.Model):
    """排课周期（销售用：一周期=一周；发布时做日期映射）"""
    PATTERN_WEEKLY = 'weekly'        # 春/秋：按周
    PATTERN_AB_FIXED6 = 'ab_fixed6'  # 暑：上六休一（默认周日休息）
    PATTERN_AB_CUSTOM = 'ab_custom'  # 冬：AB 不规则
    PATTERN_CHOICES = (
        (PATTERN_WEEKLY, 'weekly'),
        (PATTERN_AB_FIXED6, 'ab_fixed6'),
        (PATTERN_AB_CUSTOM, 'ab_custom'),
    )

    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name='cycles')
    term_type = models.CharField(max_length=10, choices=TERM_TYPE, db_index=True)
    year = models.PositiveSmallIntegerField(db_index=True)
    campus = models.ForeignKey('schedule.Campus', on_delete=models.PROTECT, related_name='cycles')

    name = models.CharField(max_length=80)
    date_from = models.DateField()
    date_to = models.DateField()
    pattern = models.CharField(max_length=20, choices=PATTERN_CHOICES, default=PATTERN_WEEKLY)
    rest_weekday = models.PositiveSmallIntegerField(default=7)  # 1~7(周一~周日)，暑假默认 7(周日休息)

    status = models.CharField(max_length=12, default='draft')   # draft/published/closed
    remark = models.CharField(max_length=200, blank=True, default='')

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'edu_cycle'
        ordering = ['-year', '-date_from']
        indexes = [models.Index(fields=['year', 'term_type', 'campus'])]

    def __str__(self):
        return f'Cycle<{self.id}> {self.name}'


class CycleRoster(models.Model):
    """周期名册（计划层，发布前不影响签到）"""
    TYPE_NORMAL = 'normal'
    TYPE_TRIAL = 'trial'
    TYPE_CHOICES = (
        (TYPE_NORMAL, 'normal'),
        (TYPE_TRIAL, 'trial'),
    )

    TRACK_CHOICES = (('A', 'A'), ('B', 'B'))

    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name='rosters')
    class_group = models.ForeignKey(ClassGroup, on_delete=models.PROTECT, related_name='cycle_rosters')
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='cycle_rosters')
    type = models.CharField(max_length=10, choices=TYPE_CHOICES, default=TYPE_NORMAL)
    track = models.CharField(max_length=1, choices=TRACK_CHOICES, null=True, blank=True)

    note = models.CharField(max_length=200, blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_cycle_roster'
        unique_together = ('cycle', 'class_group', 'student', 'track')
        indexes = [
            models.Index(fields=['cycle', 'class_group']),
            models.Index(fields=['student']),
        ]


class CyclePublishLog(models.Model):
    """发布日志（记录映射与差异，便于审计/回滚）"""
    SCOPE_FUTURE = 'future_only'
    SCOPE_INCLUDE_TODAY = 'include_today'
    MODE_PARTICIPANTS = 'participants'
    MODE_SEGMENT_ENROLL = 'segment_enroll'  # 备用，不在本期启用

    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name='publish_logs')
    scope = models.CharField(max_length=20, default=SCOPE_FUTURE)
    mode = models.CharField(max_length=20, default=MODE_PARTICIPANTS)
    payload = JSONTextField(default=dict)     # SQLite 兼容：存 JSON 文本，读写自动 dict
    diff_stats = JSONTextField(default=dict)  # 同上
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_cycle_publish_log'
        ordering = ['-id']


class CyclePublishItem(models.Model):
    """追踪“本周期发布”创建的明细（仅删除本周期所生，避免误删手工或其它周期）"""
    cycle = models.ForeignKey(Cycle, on_delete=models.CASCADE, related_name='publish_items')
    roster = models.ForeignKey(CycleRoster, on_delete=models.CASCADE, related_name='publish_items')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='cycle_publish_items')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='cycle_publish_items')
    participant = models.ForeignKey('schedule.LessonParticipant', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    type = models.CharField(max_length=10, choices=CycleRoster.TYPE_CHOICES)   # normal/trial
    track = models.CharField(max_length=1, null=True, blank=True)              # A/B
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_cycle_publish_item'
        unique_together = ('cycle', 'lesson', 'student')
        indexes = [
            models.Index(fields=['cycle', 'lesson']),
            models.Index(fields=['student']),
        ]

class CyclePreplanSlot(models.Model):
    """
    预排槽位：把某个班级放到【周几 × 时间段】的“缓冲池”里。
    —— 只存计划，不生成 Lesson；发布时再映射到具体自然日。
    """
    cycle = models.ForeignKey('schedule.Cycle', on_delete=models.CASCADE, related_name='preplan_slots')
    class_group = models.ForeignKey('schedule.ClassGroup', on_delete=models.PROTECT, related_name='preplan_slots')

    # 1~7（周一~周日），与前端看板一致；默认周日休息
    weekday = models.PositiveSmallIntegerField()

    # 允许自定义时间（满足你“可改时间”的要求）；发布匹配 Lesson 用它
    start_time = models.TimeField()
    end_time = models.TimeField()

    # 可选：预排阶段覆盖老师/教室（不改动班级默认；发布时仅用于冲突提示或后续扩展）
    teacher_override = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    room_override = models.ForeignKey('schedule.Room', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    note = models.CharField(max_length=200, blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_cycle_preplan_slot'
        ordering = ['cycle_id','weekday','start_time','id']
        indexes = [
            models.Index(fields=['cycle', 'weekday']),
            models.Index(fields=['class_group']),
        ]
        # 同一张预排表里，不允许同一个班在同一周几同一时间段重复摆放
        unique_together = ('cycle', 'class_group', 'weekday', 'start_time', 'end_time')

    def __str__(self):
        return f'Preplan<{self.id}> cyc={self.cycle_id} cg={self.class_group_id} w{self.weekday} {self.start_time}-{self.end_time}'