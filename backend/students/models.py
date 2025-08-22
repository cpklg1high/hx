from django.db import models
from django.contrib.auth import get_user_model
import json

User = get_user_model()

# ================= 字典枚举 =================

GRADE_CHOICES = (
    (1, '一年级'), (2, '二年级'), (3, '三年级'), (4, '四年级'), (5, '五年级'), (6, '预初'),
    (7, '初一'), (8, '初二'), (9, '初三'),
    (10, '高一'), (11, '高二'), (12, '高三'),
)

RELATION_CHOICES = (
    ('father', '父亲'),
    ('mother', '母亲'),
    ('other', '其他'),
)

VISIT_CHANNEL = (
    ('referral', '转介绍'),
    ('walk_in', '直访'),
    ('other', '其他'),
)

ACADEMIC_STATUS = (
    ('active', '在读'),
    ('paused', '停课'),
    ('finished', '结课'),
    ('refunded', '退费清'),
    ('inactive', '潜在'),
)

# ================= 学校 =================

class School(models.Model):
    name = models.CharField(max_length=100, unique=True)
    # 用于排序/搜索的拼音（手动维护或通过数据迁移写入）
    pinyin = models.CharField(max_length=120, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_school'
        ordering = ['pinyin', 'name']

    def __str__(self):
        return self.name

# ================= 主实体：学生/监护人等 =================

class Student(models.Model):
    name = models.CharField(max_length=50)
    grade = models.PositiveSmallIntegerField(choices=GRADE_CHOICES)

    # 新增：所属学校（必填），外键约束，学校被使用时不允许删除
    school = models.ForeignKey(School, on_delete=models.PROTECT, related_name='students')

    academic_status = models.CharField(max_length=16, choices=ACADEMIC_STATUS, default='inactive')

    current_salesperson = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        limit_choices_to={'role': 'salesperson'},
        related_name='students_following'
    )

    # 来访渠道
    visit_channel = models.CharField(max_length=16, choices=VISIT_CHANNEL)
    referral_student = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='referral_children'
    )
    visit_channel_other_text = models.CharField(max_length=100, null=True, blank=True)

    remark = models.CharField(max_length=500, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    updated_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')

    class Meta:
        db_table = 'edu_student'
        ordering = ['-id']

    def __str__(self):
        return f'{self.id} - {self.name}'

class Guardian(models.Model):
    name = models.CharField(max_length=50, blank=True, default='')
    phone = models.CharField(max_length=20)  # 不唯一（按你的规则）
    wechat = models.CharField(max_length=50, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_guardian'
        indexes = [models.Index(fields=['phone'])]

    def __str__(self):
        return f'{self.name or ""} {self.phone}'

class StudentGuardian(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='guardian_links')
    guardian = models.ForeignKey(Guardian, on_delete=models.CASCADE, related_name='student_links')
    relation_code = models.CharField(max_length=10, choices=RELATION_CHOICES)
    is_primary = models.BooleanField(default=False)
    remark = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        db_table = 'edu_student_guardian'
        constraints = [
            models.UniqueConstraint(fields=['student', 'guardian'], name='uniq_student_guardian'),
        ]

class StudentAdvisorHistory(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='advisor_histories')
    salesperson = models.ForeignKey(User, on_delete=models.CASCADE, related_name='advisor_changes')
    start_at = models.DateTimeField()
    end_at = models.DateTimeField(null=True, blank=True)
    change_reason = models.CharField(max_length=200, blank=True, default='')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'edu_student_advisor_history'
        indexes = [models.Index(fields=['student', 'start_at'])]

# ================= 转介绍奖励表 =================

class ReferralReward(models.Model):
    STATUS = (
        ('pending', '待审核'),
        ('approved', '已审核'),
        ('rejected', '已驳回'),
        ('paid', '已发放'),
    )

    referrer_student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='referral_rewards_from')
    new_student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='referral_reward')  # 1 对 1
    status = models.CharField(max_length=10, choices=STATUS, default='pending')

    # JSON 改为文本存储
    rule_snapshot = models.TextField(blank=True, default='')
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    paid_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reason = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        db_table = 'edu_referral_reward'
        indexes = [models.Index(fields=['status', 'created_at'])]

    def __str__(self):
        return f'ReferralReward<{self.id}> {self.referrer_student_id} -> {self.new_student_id} [{self.status}]'

    # ---- 便捷方法：dict <-> JSON 文本 ----
    def set_rule_snapshot(self, data):
        self.rule_snapshot = json.dumps(data or {}, ensure_ascii=False)

    def get_rule_snapshot(self):
        try:
            return json.loads(self.rule_snapshot) if self.rule_snapshot else None
        except Exception:
            return None
