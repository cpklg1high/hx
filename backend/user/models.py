from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', '管理员'),
        ('teacher', '教师'),
        ('teacher_manager', '教学主管'),
        ('salesperson', '班主任'),
        ('salesperson_manager', '班主任主管'),
        ('parent', '家长'),
    )
    name = models.CharField(max_length=255, null=True, blank=True)
    avatar = models.CharField(max_length=255, null=True, blank=True )
    phone_number = models.CharField(max_length=11, null=True, blank=True)
    status = models.IntegerField(default=1, choices=((1, "正常"), (0, "禁用")), verbose_name="状态")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, null=True, blank=True , verbose_name="角色")
    remark = models.CharField(max_length=500, null=True, blank=True)
    login_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sys_user'  # 与课程表命名对齐
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return self.username