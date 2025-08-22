from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple, Optional
from django.db.models import Q
from django.utils import timezone

from .models import Lesson, ClassGroup
from academics.models import Enrollment

# —— 周几 <-> 位掩码（bit0=周一 ... bit6=周日）
def days_to_mask(days: List[int]) -> int:
    m = 0
    for d in days:
        if 1 <= d <= 7:
            m |= (1 << (d-1))
    return m

def mask_to_days(mask: int) -> List[int]:
    return [i+1 for i in range(7) if mask & (1 << i)]

def dt_combine(d, t):
    tz = timezone.get_current_timezone()
    return timezone.make_aware(datetime.combine(d, t), tz)

# —— 时长换算
def round_to_half_hours(minutes: int) -> Decimal:
    hours = Decimal(minutes) / Decimal(60)
    half = (hours * 2).quantize(Decimal('0'), rounding=ROUND_HALF_UP)
    return (half / Decimal(2)).quantize(Decimal('0.00'))

def get_student_deduct(course_mode: str, duration_minutes: int) -> Tuple[str, Decimal]:
    """
    返回 (unit, qty)；small_class 按 1 节；1v1/1v2 按时长小时，四舍五入到 0.5
    """
    if course_mode == 'small_class':
        return 'sessions', Decimal('1.00')
    return 'hours', round_to_half_hours(duration_minutes)

# —— 容量策略
def capacity_default(course_mode: str) -> Optional[int]:
    if course_mode == 'one_to_one':
        return 1
    if course_mode == 'one_to_two':
        return 2
    return None  # small_class 不限

def capacity_max(course_mode: str) -> Optional[int]:
    if course_mode == 'one_to_one':
        return 1
    if course_mode == 'one_to_two':
        return 4
    return None  # small_class 不限

# —— 时间重叠判断与冲突
def time_overlap(start_a, end_a, start_b, end_b) -> bool:
    return (start_a < end_b) and (end_a > start_b)

def find_teacher_or_room_conflicts(teacher_id, room_id, the_date, start_time, end_time, exclude_lesson_id=None):
    qs = Lesson.objects.filter(date=the_date).exclude(status='canceled')
    if exclude_lesson_id:
        qs = qs.exclude(id=exclude_lesson_id)
    conflicts = []
    if teacher_id:
        t_qs = qs.filter(teacher_id=teacher_id, start_time__lt=end_time, end_time__gt=start_time)
        if t_qs.exists():
            conflicts.append({'type': 'teacher', 'lesson_ids': list(t_qs.values_list('id', flat=True))})
    if room_id:
        r_qs = qs.filter(room_id=room_id, start_time__lt=end_time, end_time__gt=start_time)
        if r_qs.exists():
            conflicts.append({'type': 'room', 'lesson_ids': list(r_qs.values_list('id', flat=True))})
    return conflicts

def student_has_conflict(student_id: int, lesson: Lesson, class_group_id: int) -> bool:
    # 学生在同日同时间段其它班级是否有课（不含当前班级）
    qs = Lesson.objects.filter(
        class_group__student_enrollments__student_id=student_id,
        class_group__student_enrollments__left_at__isnull=True,
        date=lesson.date
    ).exclude(class_group_id=class_group_id).exclude(status='canceled').distinct()
    qs = qs.filter(start_time__lt=lesson.end_time, end_time__gt=lesson.start_time)
    return qs.exists()

# —— 扣课前校验与执行
def ensure_enrollment(student_id: int, course_mode: str, unit: str) -> Enrollment:
    en, _ = Enrollment.objects.get_or_create(
        student_id=student_id, course_mode=course_mode,
        defaults={'deduct_unit': unit, 'status': 'active'}
    )
    if en.deduct_unit != unit:
        en.deduct_unit = unit
        en.save(update_fields=['deduct_unit'])
    return en

def check_balance_sufficient(student_id: int, course_mode: str, unit: str, qty: Decimal) -> bool:
    en = ensure_enrollment(student_id, course_mode, unit)
    if unit == 'hours':
        paid = Decimal(en.remaining_hours or 0)
        gift = Decimal(getattr(en, 'remaining_hours_gift', 0) or 0)
    else:
        paid = Decimal(en.remaining_sessions or 0)
        gift = Decimal(getattr(en, 'remaining_sessions_gift', 0) or 0)
    return (paid + gift) >= qty

def apply_deduction(student_id: int, course_mode: str, unit: str, qty: Decimal) -> Tuple[Decimal, Decimal, str]:
    """
    先扣付费，再扣赠送；返回 (paid_used, gift_used, main_source)
    """
    en = ensure_enrollment(student_id, course_mode, unit)
    if unit == 'hours':
        paid_bal = Decimal(en.remaining_hours or 0)
        gift_bal = Decimal(getattr(en, 'remaining_hours_gift', 0) or 0)
    else:
        paid_bal = Decimal(en.remaining_sessions or 0)
        gift_bal = Decimal(getattr(en, 'remaining_sessions_gift', 0) or 0)

    need = qty
    paid_used = min(paid_bal, need)
    need -= paid_used
    gift_used = min(gift_bal, need)
    need -= gift_used

    if need > 0:
        raise ValueError('余额不足')  # 调用方已预检，这里理论不会触发

    # 写回
    if unit == 'hours':
        en.remaining_hours = (paid_bal - paid_used)
        en.remaining_hours_gift = (gift_bal - gift_used)
        en.save(update_fields=['remaining_hours', 'remaining_hours_gift'])
    else:
        en.remaining_sessions = (paid_bal - paid_used)
        en.remaining_sessions_gift = (gift_bal - gift_used)
        en.save(update_fields=['remaining_sessions', 'remaining_sessions_gift'])

    main = 'paid' if paid_used > 0 else 'gift'
    return (paid_used.quantize(Decimal('0.00')), gift_used.quantize(Decimal('0.00')), main)

def revert_deduction(student_id: int, course_mode: str, unit: str, paid_used: Decimal, gift_used: Decimal):
    en = ensure_enrollment(student_id, course_mode, unit)
    if unit == 'hours':
        en.remaining_hours = Decimal(en.remaining_hours or 0) + (paid_used or 0)
        en.remaining_hours_gift = Decimal(getattr(en, 'remaining_hours_gift', 0) or 0) + (gift_used or 0)
        en.save(update_fields=['remaining_hours', 'remaining_hours_gift'])
    else:
        en.remaining_sessions = Decimal(en.remaining_sessions or 0) + (paid_used or 0)
        en.remaining_sessions_gift = Decimal(getattr(en, 'remaining_sessions_gift', 0) or 0) + (gift_used or 0)
        en.save(update_fields=['remaining_sessions', 'remaining_sessions_gift'])
