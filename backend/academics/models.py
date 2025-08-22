# backend/academics/models.py
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


class Enrollment(models.Model):
    """
    学生在读账户（按班型分账）：
    - one_to_one / one_to_two 用 hours（小时）
    - small_class 用 sessions（节/次）
    - 付费余额与赠送余额分开统计，便于退款时只按付费余额核算
    """

    # 归属学生
    student = models.ForeignKey('students.Student', on_delete=models.CASCADE, related_name='enrollments')

    # 班型（新增）
    COURSE_MODE_CHOICES = (
        ('one_to_one', '一对一'),
        ('one_to_two', '一对二'),
        ('small_class', '小班'),
    )
    course_mode = models.CharField(max_length=20, choices=COURSE_MODE_CHOICES, default='one_to_one', db_index=True)

    # 扣课单位：one_to_one/one_to_two = hours；small_class = sessions
    DEDUCT_UNIT = (('hours', '小时'), ('sessions', '节数'))
    deduct_unit = models.CharField(max_length=16, choices=DEDUCT_UNIT)

    # -------- 付费购买 & 剩余（按单位二选一）--------
    purchased_hours = models.DecimalField(max_digits=7, decimal_places=2, default=0)   # 购买总小时（含历史）
    remaining_hours = models.DecimalField(max_digits=7, decimal_places=2, default=0)   # 剩余小时（仅付费部分）

    purchased_sessions = models.PositiveIntegerField(default=0)   # 购买总节数（含历史）
    remaining_sessions = models.PositiveIntegerField(default=0)   # 剩余节数（仅付费部分）

    # -------- 新增：赠送余额（与付费余额分开）--------
    # 小班常用；小时类通常为 0，但保留字段便于兼容特殊活动
    remaining_hours_gift = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    remaining_sessions_gift = models.PositiveIntegerField(default=0)

    # 状态
    STATUS = (
        ('active', '在读'),
        ('paused', '停课'),
        ('finished', '结课'),
        ('refunded', '已退费'),
        ('closed', '关闭'),
    )
    status = models.CharField(max_length=16, choices=STATUS, default='active')

    # 过期日（可选）
    expire_at = models.DateField(null=True, blank=True)

    # 金额累计（只统计“实付”总额，用于财务口径；退款会相应扣减）
    amount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # 创建时间
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_enrollment'
        indexes = [
            models.Index(fields=['student', 'status']),
        ]
        # 关键唯一约束：同一个“学生+班型+在读状态”只能有一条账户，避免混账
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'course_mode', 'status'],
                name='uniq_student_mode_active',
                condition=Q(status='active')
            )
        ]

    def __str__(self):
        return f"Enrollment<{self.id}> S{self.student_id} mode={self.course_mode} unit={self.deduct_unit} status={self.status}"

    @staticmethod
    def is_student_studying(student_id: int) -> bool:
        """判断学生是否有可用余额（在读 & 未过期 & 有剩余）"""
        today = timezone.localdate()
        qs = Enrollment.objects.filter(student_id=student_id, status='active').filter(
            Q(deduct_unit='hours', remaining_hours__gt=0) |
            Q(deduct_unit='sessions', remaining_sessions__gt=0)
        ).filter(
            Q(expire_at__isnull=True) | Q(expire_at__gte=today)
        )
        return qs.exists()
