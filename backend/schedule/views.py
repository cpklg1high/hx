from datetime import timedelta
from decimal import Decimal
from typing import List, Dict
from collections import defaultdict

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    Term, Room, Subject, ClassGroup, Lesson,
    ClassEnrollment, LessonLeave, Attendance,
    TeacherWorklog,LessonParticipant
)
from .serializers import (
    TermIn, TermOut, ClassGroupCreateIn, ClassGroupOut,
    EnrollIn, UnenrollIn, LessonsQuery, LeaveIn, AttendanceCommitIn,
    AttendanceOut,LessonParticipantSerializer
)
from .utils import (
    get_student_deduct, find_teacher_or_room_conflicts, student_has_conflict,
    capacity_default, capacity_max, dt_combine, check_balance_sufficient, apply_deduction, revert_deduction,
    round_to_half_hours
)

User = get_user_model()


def ok(data=None, message='OK'): return Response({'code': 200, 'message': message, 'data': data or {}})


def bad(message='参数错误', code=400): return Response({'code': code, 'message': message}, status=code)


def user_has_role(user, roles: List[str]) -> bool:
    return getattr(user, 'role', None) in roles


def is_admin(user) -> bool:
    return user_has_role(user, ['admin'])


# --------- 基础字典 ---------
class TermListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Term.objects.all().order_by('-year','-start_date')
        return ok([{'id':t.id,'name':t.name,'type':t.type,'year':t.year,
                    'start_date':str(t.start_date),'end_date':str(t.end_date),
                    'is_active':t.is_active,'remark':t.remark} for t in qs])

    def post(self, request):
        # 仅 admin / teacher_manager 可创建
        if not user_has_role(request.user, ['admin','teacher_manager']):
            return bad('无权限', 403)
        from .serializers import TermIn, TermOut
        s = TermIn(data=request.data)
        s.is_valid(raise_exception=True)
        t = s.save()
        return ok(TermOut(t).data, '创建成功')


class RoomList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Room.objects.filter(is_active=True).order_by('name')
        return ok([{'id': r.id, 'name': r.name, 'capacity': r.capacity, 'location': r.location} for r in qs])

    def post(self, request):
        if not user_has_role(request.user, ['admin', 'teacher_manager']):
            return bad('无权限', 403)
        name = (request.data.get('name') or '').strip()
        if not name:
            return bad('name 必填', 400)
        capacity = request.data.get('capacity', None)
        location = request.data.get('location', '') or ''
        obj, created = Room.objects.get_or_create(
            name=name,
            defaults={'capacity': capacity, 'location': location, 'is_active': True}
        )
        if not created:
            if capacity is not None:
                obj.capacity = capacity
            obj.location = location
            obj.is_active = True
            obj.save()
        return ok({'id': obj.id, 'name': obj.name, 'capacity': obj.capacity, 'location': obj.location},
                  '创建成功' if created else '已存在，已返回/更新')


class SubjectList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Subject.objects.all().order_by('name')
        return ok([{'id': s.id, 'name': s.name, 'phase': s.phase} for s in qs])

    def post(self, request):
        if not user_has_role(request.user, ['admin', 'teacher_manager']):
            return bad('无权限', 403)
        name = (request.data.get('name') or '').strip()
        phase = (request.data.get('phase') or 'junior').strip()
        if not name:
            return bad('name 必填', 400)
        if phase not in ('primary', 'junior', 'senior'):
            return bad('phase 必须是 primary/junior/senior', 400)
        obj, created = Subject.objects.get_or_create(name=name, defaults={'phase': phase})
        if not created and obj.phase != phase:
            obj.phase = phase
            obj.save(update_fields=['phase'])
        return ok({'id': obj.id, 'name': obj.name, 'phase': obj.phase},
                  '创建成功' if created else '已存在，已返回/更新')


class TeacherList(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 根据你的用户模型：role='teacher'
        qs = User.objects.filter(is_active=True)
        role_field = hasattr(User, 'role')
        if role_field:
            qs = qs.filter(role='teacher')
        qs = qs.order_by('id')
        return ok([{'id': u.id, 'name': getattr(u, 'name', None) or u.username} for u in qs])


class LessonsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        s = LessonsQuery(data=request.query_params)
        s.is_valid(raise_exception=True)
        v = s.validated_data

        qs = (
            Lesson.objects
            .filter(
                class_group__term_id=v['term_id'],
                date__gte=v['date_from'],
                date__lte=v['date_to']
            )
            .exclude(status='canceled')
            .select_related('class_group', 'class_group__subject', 'teacher', 'room')
            .order_by('date', 'start_time', 'id')
        )

        # 过滤条件保持不变
        if v.get('grades'):
            qs = qs.filter(class_group__grade__in=v['grades'])
        if v.get('teachers'):
            qs = qs.filter(teacher_id__in=v['teachers']) | qs.filter(class_group__teacher_main_id__in=v['teachers'])
        if v.get('subjects'):
            qs = qs.filter(class_group__subject_id__in=v['subjects'])

        # —— 批量取当页涉及的班级与课次 ——
        cg_ids = set(qs.values_list('class_group_id', flat=True))
        lesson_ids = set(qs.values_list('id', flat=True))

        # —— 一次性取出“全部学生”（在读）：构建 {cg_id: [ {id, name}, ... ]} ——
        from collections import defaultdict
        by_cg_students = defaultdict(list)
        if cg_ids:
            enroll_rows = (
                ClassEnrollment.objects
                .filter(class_group_id__in=cg_ids, left_at__isnull=True)
                .select_related('student')
                .values('class_group_id', 'student_id', 'student__name')
                .order_by('id')
            )
            for row in enroll_rows:
                by_cg_students[row['class_group_id']].append(
                    {'id': row['student_id'], 'name': row['student__name'] or ''}
                )

        # —— 批量统计请假数，避免循环 count ——
        from django.db.models import Count
        leaves_map = {lid: 0 for lid in lesson_ids}
        if lesson_ids:
            for r in (LessonLeave.objects
                      .filter(lesson_id__in=lesson_ids)
                      .values('lesson_id')
                      .annotate(cnt=Count('id'))):
                leaves_map[r['lesson_id']] = r['cnt']

        # —— 组装返回（新增 roster 完整数组；保留 roster_preview/roster_count/enrolled）——
        data = []
        for les in qs:
            cg = les.class_group
            teacher = les.teacher or cg.teacher_main
            room = les.room or cg.room_default

            roster = by_cg_students.get(cg.id, [])               # 全量学生 [{id,name}, ...]
            roster_count = len(roster)
            roster_preview = [s['name'] for s in roster][:5]
            leave_count = leaves_map.get(les.id, 0)

            data.append({
                'id': les.id,
                'class_group_id': cg.id,
                'title': f'{cg.name or ""}{cg.subject.name}-{cg.course_mode}',
                'date': str(les.date),
                'start_time': str(les.start_time),
                'end_time': str(les.end_time),
                'duration': les.duration_minutes,
                'grade': cg.grade,
                'course_mode': cg.course_mode,
                'subject': cg.subject.name,
                'room': (room.name if room else None),
                'teacher': (getattr(teacher, 'name', None) or getattr(teacher, 'username', None)),

                # ✅ 新增：完整学生数组（全量）
                'roster': roster,                  # [{id, name}, ...]

                # 兼容 & 汇总
                'roster_preview': roster_preview,  # 预览（前5个名字）
                'roster_count': roster_count,      # 总人数
                'enrolled': roster_count,          # 保持前端已用的字段
                'capacity': cg.capacity,           # small_class 为 null
                'leave_count': leave_count,
                'status': les.status,
            })

        return ok(data)


# --------- 班级 ---------
class ClassGroupListCreate(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        term_id = request.query_params.get('term_id')
        qs = ClassGroup.objects.all().order_by('-id')
        if term_id:
            qs = qs.filter(term_id=term_id)
        # 可选更多筛选：grade/subject/teacher
        data = [ClassGroupOut(i).data for i in qs]
        return ok(data)

    def post(self, request):
        if not user_has_role(request.user, ['admin', 'teacher_manager']):
            return bad('无权限', 403)
        s = ClassGroupCreateIn(data=request.data)
        s.is_valid(raise_exception=True)
        cg = s.save()
        return ok(ClassGroupOut(cg).data, '创建成功')


class ClassGroupEnroll(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not user_has_role(request.user, ['admin', 'teacher_manager', 'salesperson']):
            return bad('无权限', 403)
        try:
            cg = ClassGroup.objects.get(id=pk)
        except ClassGroup.DoesNotExist:
            return bad('班级不存在', 404)
        s = EnrollIn(data=request.data)
        s.is_valid(raise_exception=True)
        student_ids = s.validated_data['student_ids']

        # 容量校验
        if cg.course_mode == 'one_to_one':
            cap = 1
        elif cg.course_mode == 'one_to_two':
            cap = cg.capacity or capacity_default('one_to_two')
            cap = min(cap, capacity_max('one_to_two'))
        else:
            cap = None

        with transaction.atomic():
            # 当前有效人数
            curr = ClassEnrollment.objects.filter(class_group=cg, left_at__isnull=True).count()
            if cap is not None and (curr + len(student_ids) > cap):
                return bad(f'容量超限：当前{curr}，新增{len(student_ids)}，上限{cap}')

            # 冲突校验：学生时间撞课
            conflicts = {}
            sample_lesson = cg.lessons.first()
            for sid in student_ids:
                # 遍历本班全部课次，任一重叠即冲突
                hit = False
                for les in cg.lessons.exclude(status='canceled'):
                    if student_has_conflict(sid, les, cg.id):
                        conflicts.setdefault(str(sid), []).append(les.id)
                        hit = True
                        break
                if hit:
                    continue

            if conflicts:
                return Response({'code': 400, 'message': '学生时间冲突', 'data': conflicts}, status=400)

            # 写入关系
            created = 0
            for sid in student_ids:
                obj, created_flag = ClassEnrollment.objects.get_or_create(student_id=sid, class_group=cg,
                                                                          left_at__isnull=True)
                if created_flag: created += 1

        return ok({'created': created}, '加入成功')


class ClassGroupUnenroll(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not user_has_role(request.user, ['admin', 'teacher_manager', 'salesperson']):
            return bad('无权限', 403)
        try:
            cg = ClassGroup.objects.get(id=pk)
        except ClassGroup.DoesNotExist:
            return bad('班级不存在', 404)
        s = UnenrollIn(data=request.data)
        s.is_valid(raise_exception=True)
        student_ids = s.validated_data['student_ids']
        n = ClassEnrollment.objects.filter(class_group=cg, student_id__in=student_ids, left_at__isnull=True) \
            .update(left_at=timezone.now())
        return ok({'updated': n}, '移除成功')



# --------- 请假（课前；一键支持 all=true） ---------
def _is_homeroom_or_admin(user, student_id: int) -> bool:
    # 你的 Student 有 current_salesperson 字段；若没有，请改成你实际的“班主任字段”
    try:
        from students.models import Student
        stu = Student.objects.get(id=student_id)
        csr_id = getattr(stu, 'current_salesperson_id', None)
    except Exception:
        csr_id = None
    if user_has_role(user, ['admin', 'teacher_manager']):
        return True
    # 你要求“所有班主任都可操作”：这里放宽为 salesperson 角色均可
    if user_has_role(user, ['salesperson']):
        return True
    return False


class LessonLeaveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # 课前设置请假
        try:
            les = Lesson.objects.select_related('class_group').get(id=pk)
        except Lesson.DoesNotExist:
            return bad('课次不存在', 404)

        # 时间限制：必须在课前
        if timezone.now() >= dt_combine(les.date, les.start_time):
            return bad('已到上课时间，不能设置请假', 400)

        s = LeaveIn(data=request.data)
        s.is_valid(raise_exception=True)
        all_flag = s.validated_data.get('all', False)
        reason = s.validated_data.get('reason', '')

        if all_flag:
            student_ids = list(ClassEnrollment.objects.filter(class_group=les.class_group, left_at__isnull=True)
                               .values_list('student_id', flat=True))
        else:
            student_ids = s.validated_data.get('student_ids', []) or []

        if not student_ids:
            return bad('未指定学生', 400)

        # 权限：对每位学生校验
        for sid in student_ids:
            if not _is_homeroom_or_admin(request.user, sid):
                return bad('无权限：仅 admin/teacher_manager/班主任可请假', 403)

        created = 0
        with transaction.atomic():
            for sid in student_ids:
                _, c = LessonLeave.objects.get_or_create(
                    lesson=les, student_id=sid, defaults={'reason': reason, 'operator': request.user})
                if c: created += 1

        return ok({'created': created}, '请假已记录')

    def delete(self, request, pk):
        # 课前撤销请假
        try:
            les = Lesson.objects.get(id=pk)
        except Lesson.DoesNotExist:
            return bad('课次不存在', 404)
        if timezone.now() >= dt_combine(les.date, les.start_time):
            return bad('已到上课时间，不能撤销请假', 400)

        s = LeaveIn(data=request.data)
        s.is_valid(raise_exception=True)
        all_flag = s.validated_data.get('all', False)

        if all_flag:
            qs = LessonLeave.objects.filter(lesson=les)
        else:
            student_ids = s.validated_data.get('student_ids', []) or []
            if not student_ids:
                return bad('未指定学生', 400)
            for sid in student_ids:
                if not _is_homeroom_or_admin(request.user, sid):
                    return bad('无权限：仅 admin/teacher_manager/班主任可操作', 403)
            qs = LessonLeave.objects.filter(lesson=les, student_id__in=student_ids)

        n = qs.delete()[0]
        return ok({'deleted': n}, '已撤销')


# --------- 签到/消课（课后；一键支持 all_present） ---------
class AttendanceCommitView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """查看名单：返回本班有效学生 + leave/已签到状态"""
        try:
            les = Lesson.objects.select_related('class_group').get(id=pk)
        except Lesson.DoesNotExist:
            return bad('课次不存在', 404)

        # 有效学生（上课时间点在班级中）
        start_dt = dt_combine(les.date, les.start_time)
        members = ClassEnrollment.objects.filter(class_group=les.class_group, left_at__isnull=True)
        stu_ids = list(members.values_list('student_id', flat=True))

        leaves = set(
            LessonLeave.objects.filter(lesson=les, student_id__in=stu_ids).values_list('student_id', flat=True))
        signed = Attendance.objects.filter(lesson=les).values('student_id', 'status')
        signed_map = {i['student_id']: i['status'] for i in signed}

        # 组装
        from students.models import Student
        students = Student.objects.filter(id__in=stu_ids).values('id', 'name')
        data = []
        for s in students:
            data.append({'student_id': s['id'], 'student_name': s['name'],
                         'status': signed_map.get(s['id']),
                         'preleave': (s['id'] in leaves)})
        return ok({'lesson': les.id, 'students': data})

    def post(self, request, pk):
        # 权限：任课老师/teacher_manager/admin
        try:
            les = Lesson.objects.select_related('class_group', 'teacher').get(id=pk)
        except Lesson.DoesNotExist:
            return bad('课次不存在', 404)

        teacher_id = (les.teacher_id or les.class_group.teacher_main_id)
        if not (is_admin(request.user) or user_has_role(request.user,
                                                        ['teacher_manager']) or request.user.id == teacher_id):
            return bad('无权限：仅任课老师/teacher_manager/admin 可提交', 403)

        # 时间限制：仅课后
        if timezone.now() <= dt_combine(les.date, les.end_time):
            return bad('尚未到下课时间，不能提交签到', 400)

        if les.lock_attendance:
            return bad('已提交过签到，无法重复提交', 400)

        s = AttendanceCommitIn(data=request.data)
        s.is_valid(raise_exception=True)
        v = s.validated_data

        # 学生清单
        members = list(
            ClassEnrollment.objects.filter(class_group=les.class_group, left_at__isnull=True).values_list('student_id',
                                                                                                          flat=True))
        if not members:
            return bad('班内无学生', 400)

        # 已请假
        pre_leaves = set(
            LessonLeave.objects.filter(lesson=les, student_id__in=members).values_list('student_id', flat=True))

        # 组装最终状态
        final = {sid: ('leave' if sid in pre_leaves else 'absent') for sid in members}

        # 一键签到：全部置为 present（已请假的仍保持 leave）
        if v.get('all_present'):
            for sid in members:
                if sid not in pre_leaves:
                    final[sid] = 'present'

        # 明细覆盖
        items = v.get('items') or []
        for it in items:
            sid = it['student_id']
            if sid in final:
                final[sid] = it['status']

        # 扣课口径
        unit, qty = get_student_deduct(les.class_group.course_mode, les.duration_minutes)

        # 预检余额（仅 present）
        insufficient = []
        for sid, st in final.items():
            if st == 'present' and not check_balance_sufficient(sid, les.class_group.course_mode, unit, qty):
                insufficient.append(sid)
        if insufficient:
            return Response({'code': 400, 'message': '部分学生余额不足', 'data': {'insufficient': insufficient}},
                            status=400)

        # 入库：Attendance + 扣课 + 工时（事务）
        with transaction.atomic():
            records = []
            for sid, st in final.items():
                paid_used = gift_used = None
                deduct_from = None
                if st == 'present':
                    paid_used, gift_used, deduct_from = apply_deduction(sid, les.class_group.course_mode, unit, qty)
                att = Attendance.objects.create(
                    lesson=les, student_id=sid, status=st,
                    deduct_unit=(unit if st == 'present' else None),
                    deduct_qty=(qty if st == 'present' else None),
                    deduct_from=deduct_from,
                    paid_used=paid_used, gift_used=gift_used,
                    operator=request.user, confirmed_at=timezone.now()
                )
                records.append(att.id)

            # 工时：小班=2小时；其它按时长（四舍五入0.5）
            work_hours = Decimal('2.00') if les.class_group.course_mode == 'small_class' else round_to_half_hours(
                les.duration_minutes)
            TeacherWorklog.objects.update_or_create(
                lesson=les, teacher_id=teacher_id,
                defaults={'work_hours': work_hours,
                          'rule_code': ('small_class_x2' if les.class_group.course_mode == 'small_class' else 'normal')}
            )

            les.status = 'finished'
            les.lock_attendance = True
            les.save(update_fields=['status', 'lock_attendance'])

        return ok({'attendance_ids': records}, '签到已提交')


class AttendanceRevertView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not is_admin(request.user):
            return bad('无权限：仅 admin 可撤销消课', 403)
        try:
            les = Lesson.objects.get(id=pk)
        except Lesson.DoesNotExist:
            return bad('课次不存在', 404)
        # 撤销：允许在任何时间，但仅当已提交过
        if not les.lock_attendance:
            return bad('该课次尚未提交签到', 400)

        atts = list(Attendance.objects.filter(lesson=les))
        with transaction.atomic():
            # 回滚扣课
            for a in atts:
                if a.status == 'present':
                    revert_deduction(a.student_id, les.class_group.course_mode, a.deduct_unit,
                                     a.paid_used or Decimal('0.00'), a.gift_used or Decimal('0.00'))
            # 删除出勤记录
            Attendance.objects.filter(lesson=les).delete()
            # 删除工时
            TeacherWorklog.objects.filter(lesson=les).delete()
            # 课次状态回滚
            les.status = 'scheduled'
            les.lock_attendance = False
            les.save(update_fields=['status', 'lock_attendance'])

        return ok(message='已撤销消课')

class StudentSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = (request.query_params.get('q') or '').strip()
        try:
            page = max(1, int(request.query_params.get('page', 1)))
        except Exception:
            page = 1
        try:
            page_size = max(1, min(50, int(request.query_params.get('page_size', 20))))
        except Exception:
            page_size = 20

        qs = Student.objects.all().order_by('id')
        if q:
            qs = qs.filter(name__icontains=q)

        total = qs.count()
        start = (page - 1) * page_size
        end = start + page_size

        # 为了兼容不同模型结构，这里逐条构建字典，避免 values() 硬编码字段名
        items = []
        for stu in qs[start:end]:
            # 学校：兼容 CharField、外键、或 school_name
            school_val = None
            if hasattr(stu, 'school'):
                v = getattr(stu, 'school')
                school_val = getattr(v, 'name', None) if v is not None else None
                if school_val is None and isinstance(v, str):
                    school_val = v
            elif hasattr(stu, 'school_name'):
                school_val = getattr(stu, 'school_name')

            # 年级：通常是整数；若模型有 grade_name 也一并返回
            grade_val = getattr(stu, 'grade', None)
            grade_name = getattr(stu, 'grade_name', None)

            items.append({
                'id': stu.id,
                'name': getattr(stu, 'name', ''),
                'grade': grade_val,
                'grade_name': grade_name,   # 没有也会是 None，前端可忽略
                'school': school_val,
            })

        return ok({
            'count': total,
            'page': page,
            'page_size': page_size,
            'results': items,
        })

class LessonParticipantViewSet(viewsets.ModelViewSet):
    """
    路由：
      GET    /api/schedule/lessons/{lesson_id}/participants
      POST   /api/schedule/lessons/{lesson_id}/participants   body: {"type":"trial|temp","students":[1,2,...]}
      DELETE /api/schedule/lessons/{lesson_id}/participants/{id}
    """
    serializer_class = LessonParticipantSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        lesson_id = self.kwargs['lesson_id']
        return LessonParticipant.objects.select_related('student').filter(lesson_id=lesson_id).order_by('id')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        lesson_id = self.kwargs['lesson_id']
        ptype = request.data.get('type')
        students = request.data.get('students', [])

        if ptype not in (LessonParticipant.TYPE_TRIAL, LessonParticipant.TYPE_TEMP):
            return Response({'code': 400, 'message': 'type 必须是 trial 或 temp', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)
        if not students or not isinstance(students, list):
            return Response({'code': 400, 'message': 'students 必须为非空数组', 'data': None},
                            status=status.HTTP_400_BAD_REQUEST)

        created = []
        # TODO: 临时排课余额校验：此处可接入你现有余额服务；当前先放行，保证可运行
        for sid in students:
            obj, _ = LessonParticipant.objects.get_or_create(
                lesson_id=lesson_id, student_id=sid,
                defaults={'type': ptype, 'created_by_id': request.user.id}
            )
            # 如果已存在且类型不同，可按需更新；这里保持幂等，不写覆盖，避免误改
            created.append(obj)

        serializer = self.get_serializer(created, many=True)
        return Response({'code': 0, 'message': 'ok', 'data': serializer.data},
                        status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'code': 0, 'message': 'deleted', 'data': None}, status=status.HTTP_200_OK)