from datetime import timedelta, date, datetime
from decimal import Decimal
from typing import List

from django.utils import timezone
from django.db import transaction
from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import (
    Term, Room, Subject, ClassGroup, ScheduleRule, ScheduleCustomEntry,
    Lesson, ClassEnrollment, LessonLeave, Attendance, TeacherWorklog,
    LessonParticipant
)
from .utils import days_to_mask, mask_to_days, find_teacher_or_room_conflicts, get_student_deduct, \
    capacity_default, capacity_max, check_balance_sufficient, apply_deduction, revert_deduction, dt_combine

User = get_user_model()


# ---------- 基础 ----------
class TermIn(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = ['name', 'type', 'year', 'start_date', 'end_date', 'remark']

    def validate(self, attrs):
        if attrs['start_date'] > attrs['end_date']:
            raise serializers.ValidationError('开始日期不能晚于结束日期')
        return attrs


class TermOut(serializers.ModelSerializer):
    class Meta:
        model = Term
        fields = ['id', 'name', 'type', 'year', 'start_date', 'end_date', 'is_active', 'remark']


# ---------- 班级创建 ----------
class WeeklyRule(serializers.Serializer):
    days = serializers.ListField(child=serializers.IntegerField(min_value=1, max_value=7), allow_empty=False)
    start_time = serializers.TimeField()
    duration_minutes = serializers.IntegerField(min_value=1)

class CustomEntry(serializers.Serializer):
    date = serializers.DateField()
    start_time = serializers.TimeField()
    duration_minutes = serializers.IntegerField(min_value=1)

class ClassGroupCreateIn(serializers.Serializer):
    term_id = serializers.IntegerField()
    course_mode = serializers.ChoiceField(choices=['one_to_one', 'one_to_two', 'small_class'])
    grade = serializers.IntegerField()  # 用你现有的 GRADE_CHOICES 值
    subject_id = serializers.IntegerField()
    room_default_id = serializers.IntegerField(required=False, allow_null=True)
    teacher_main_id = serializers.IntegerField()
    name = serializers.CharField(required=False, allow_blank=True, max_length=80)
    capacity = serializers.IntegerField(required=False, allow_null=True, min_value=1)

    rule_type = serializers.ChoiceField(choices=['weekly', 'custom'])
    weekly = WeeklyRule(required=False)
    custom = serializers.ListField(child=CustomEntry(), required=False)

    def validate(self, attrs):
        # 容量规则
        cm = attrs['course_mode']
        cap_def = capacity_default(cm)
        cap_max = capacity_max(cm)
        cap = attrs.get('capacity', None)
        if cm == 'small_class':
            attrs['capacity'] = None
        elif cm == 'one_to_one':
            attrs['capacity'] = 1
        else:  # one_to_two
            if cap is None:
                attrs['capacity'] = cap_def
            if attrs['capacity'] > cap_max:
                raise serializers.ValidationError('1v2 班级容量最多 4 人')

        # 规则校验
        rtype = attrs['rule_type']
        if rtype == 'weekly':
            w = self.initial_data.get('weekly') or {}
            if not w:
                raise serializers.ValidationError('weekly 规则缺失')
        else:
            c = self.initial_data.get('custom') or []
            if not c:
                raise serializers.ValidationError('custom 规则缺失')

        return attrs

    def create(self, validated_data):
        from .models import Term, Subject, Room
        term = Term.objects.get(id=validated_data['term_id'])
        subject = Subject.objects.get(id=validated_data['subject_id'])
        room = None
        if validated_data.get('room_default_id'):
            room = Room.objects.get(id=validated_data['room_default_id'])
        teacher = User.objects.get(id=validated_data['teacher_main_id'])

        with transaction.atomic():
            cg = ClassGroup.objects.create(
                term=term,
                course_mode=validated_data['course_mode'],
                grade=validated_data['grade'],
                subject=subject,
                room_default=room,
                teacher_main=teacher,
                name=validated_data.get('name') or '',
                capacity=validated_data.get('capacity'),
            )
            # 生成规则与课次
            if validated_data['rule_type'] == 'weekly':
                w = self.validated_data['weekly']  # ✅ 已经是 python 对象
                rule = ScheduleRule.objects.create(
                    class_group=cg, type='weekly',
                    weekly_days_mask=days_to_mask(w['days']),
                    weekly_start_time=w['start_time'],
                    weekly_duration=w['duration_minutes'],
                )
                # 在 Term 范围内展开
                self._generate_weekly_lessons(cg, rule, term)
            else:
                rule = ScheduleRule.objects.create(class_group=cg, type='custom')
                # 保存子项并生成课次（均为 python 对象）
                for e in self.validated_data['custom']:  # ✅ 不再用 initial_data
                    ce = ScheduleCustomEntry.objects.create(
                        rule=rule, date=e['date'], start_time=e['start_time'],
                        duration_minutes=e['duration_minutes']
                    )
                    self._create_lesson_or_raise(cg, ce.date, ce.start_time, e['duration_minutes'])

        return cg

    def _generate_weekly_lessons(self, cg: ClassGroup, rule: ScheduleRule, term: Term):
        days = set(mask_to_days(rule.weekly_days_mask or 0))
        if not days:
            raise serializers.ValidationError('weekly 规则的天数无效')

        d = term.start_date
        while d <= term.end_date:
            # Django: isoweekday: 周一=1 ... 周日=7
            if d.isoweekday() in days:
                self._create_lesson_or_raise(cg, d, rule.weekly_start_time, rule.weekly_duration)
            d += timedelta(days=1)

    def _create_lesson_or_raise(self, cg: ClassGroup, the_date, start_time, duration_minutes: int):
        # 计算结束时间（start_time 确保为 datetime.time）
        end_time = (datetime.combine(date.today(), start_time) + timedelta(minutes=duration_minutes)).time()

        # 老师/教室冲突（阻塞）
        conflicts = find_teacher_or_room_conflicts(
            teacher_id=cg.teacher_main_id,
            room_id=cg.room_default_id,
            the_date=the_date, start_time=start_time, end_time=end_time
        )
        if conflicts:
            raise serializers.ValidationError({'conflicts': conflicts})

        Lesson.objects.create(
            class_group=cg, date=the_date,
            start_time=start_time, end_time=end_time, duration_minutes=duration_minutes,
            room=cg.room_default, teacher=cg.teacher_main, status='scheduled'
        )


class ClassGroupOut(serializers.ModelSerializer):
    term_name = serializers.CharField(source='term.name', read_only=True)
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    room_name = serializers.SerializerMethodField()

    def get_teacher_name(self, obj):
        return getattr(obj.teacher_main, 'name', None) or getattr(obj.teacher_main, 'username', None)

    def get_room_name(self, obj):
        return obj.room_default.name if obj.room_default else None

    class Meta:
        model = ClassGroup
        fields = ['id','name','term','term_name','course_mode','grade','subject','subject_name',
                  'room_default','room_name','teacher_main','teacher_name','capacity','status','remark','created_at']


# ---------- 加/移学生 ----------
class EnrollIn(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)

class UnenrollIn(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False)


# ---------- 课表查询 ----------
class LessonsQuery(serializers.Serializer):
    term_id = serializers.IntegerField()
    date_from = serializers.DateField()
    date_to = serializers.DateField()
    view = serializers.ChoiceField(choices=['grade', 'teacher'], required=False)
    grades = serializers.ListField(child=serializers.IntegerField(), required=False)
    teachers = serializers.ListField(child=serializers.IntegerField(), required=False)
    subjects = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate(self, attrs):
        if attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError('date_from 不能晚于 date_to')
        return attrs


# ---------- 请假 ----------
class LeaveIn(serializers.Serializer):
    student_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, allow_empty=True)
    all = serializers.BooleanField(required=False, default=False)
    reason = serializers.CharField(required=False, allow_blank=True, max_length=200)


# ---------- 签到/消课 ----------
class AttendanceItem(serializers.Serializer):
    student_id = serializers.IntegerField()
    status = serializers.ChoiceField(choices=['present','leave','absent'])

class AttendanceCommitIn(serializers.Serializer):
    all_present = serializers.BooleanField(required=False, default=False)  # 一键签到（除已请假者）
    items = serializers.ListField(child=AttendanceItem(), required=False)

class AttendanceOut(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    class Meta:
        model = Attendance
        fields = ['id','student','student_name','status','deduct_unit','deduct_qty','deduct_from','paid_used','gift_used','confirmed_at','created_at']

class LessonParticipantSerializer(serializers.ModelSerializer):
    # 展示用字段（防止前端重复查学生详情）
    student_name = serializers.CharField(source='student.name', read_only=True)
    grade_id = serializers.IntegerField(source='student.grade_id', read_only=True)
    grade_name = serializers.CharField(source='student.grade_name', read_only=True, default=None)
    school = serializers.CharField(source='student.school', read_only=True, default=None)

    class Meta:
        model = LessonParticipant
        fields = (
            'id', 'lesson', 'student', 'type', 'created_at',
            'student_name', 'grade_id', 'grade_name', 'school'
        )
        read_only_fields = ('id', 'created_at')