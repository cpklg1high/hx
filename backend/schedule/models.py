from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from students.models import Student, GRADE_CHOICES  # 年级枚举与学生
from academics.models import Enrollment  # 后续签到扣课会用到（本步仅建表）

User = get_user_model()

# 班型（与 billing/academics 保持一致）
COURSE_MODE = (
    ('one_to_one', '一对一'),
    ('one_to_two', '一对二'),  # 实际容量 <= 4（默认2）
    ('small_class', '小班'),   # 无上限
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
            # 同一学生在同一班级同一时间仅允许一个“有效”（left_at is null）的关系
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
