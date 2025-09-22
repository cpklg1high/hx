from datetime import date, datetime, timedelta
from collections import defaultdict
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import (
    Campus, Cycle, CycleRoster, CyclePublishLog, CyclePublishItem,
    ClassGroup, Lesson, LessonParticipant , CyclePreplanSlot
)
from .serializers_cycle import (
    CampusSerializer, CycleSerializer, CycleRosterSerializer,
    CyclePublishLogSerializer , CycleMasterRosterItemSerializer ,
    CyclePreplanSlotSerializer
)
from .constants import TIME_SLOTS, SMALL_CLASS, NON_SMALL

def ok(data=None, message='OK', code=0, http=200):
    return Response({'code': code, 'message': message, 'data': data}, status=http)

def err(message='error', code=400, http=400, data=None):
    return Response({'code': code, 'message': message, 'data': data}, status=http)

def require_manager(user):
    # 你可以按实际角色体系替换：例如 user.is_staff or user.groups.filter(name__in=['manager','supervisor']).exists()
    return user.is_staff

class CampusListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        qs = Campus.objects.filter(is_active=True).order_by('name')
        return ok(CampusSerializer(qs, many=True).data)

class CycleListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        qs = Cycle.objects.all().order_by('-year','-date_from')
        term_type = request.query_params.get('term_type')
        year = request.query_params.get('year')
        campus_id = request.query_params.get('campus')
        if term_type: qs = qs.filter(term_type=term_type)
        if year: qs = qs.filter(year=year)
        if campus_id: qs = qs.filter(campus_id=campus_id)
        return ok(CycleSerializer(qs, many=True).data)

    def post(self, request):
        ser = CycleSerializer(data=request.data)
        if ser.is_valid():
            obj = ser.save(created_by=request.user, status='draft')
            return ok(CycleSerializer(obj).data, 'created', http=201)
        return err(ser.errors, http=400)

class CycleDetailView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        obj = Cycle.objects.filter(pk=pk).first()
        if not obj: return err('not found', 404, 404)
        return ok(CycleSerializer(obj).data)

# === 周期板数据 ===
class CycleBoardView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, pk):
        cycle = Cycle.objects.filter(pk=pk).first()
        if not cycle: return err('cycle not found', 404, 404)

        # 列：date_from ~ date_to
        dates = []
        d = cycle.date_from
        while d <= cycle.date_to:
            dates.append(str(d))
            d += timedelta(days=1)

        # 拉取该校区范围内的课次
        # 校区判断：优先 Lesson.room.campus；否则回退 class_group.room_default.campus
        lessons = (Lesson.objects
            .filter(date__gte=cycle.date_from, date__lte=cycle.date_to)
            .filter(status='scheduled')
            .select_related('class_group','teacher','room','class_group__room_default'))

        # 过滤校区
        def _lesson_in_campus(lesson):
            c = None
            if lesson.room and lesson.room.campus_id:
                c = lesson.room.campus_id
            elif lesson.class_group and lesson.class_group.room_default and lesson.class_group.room_default.campus_id:
                c = lesson.class_group.room_default.campus_id
            return c == cycle.campus_id

        lessons = [l for l in lessons if _lesson_in_campus(l)]

        # 时间档归类
        def _bucket_key(cg_mode, start, end):
            slots = TIME_SLOTS[SMALL_CLASS] if cg_mode == SMALL_CLASS else TIME_SLOTS['non_small']
            s = start.strftime('%H:%M'); e = end.strftime('%H:%M')
            for (ss,ee) in slots:
                if s >= ss and e <= ee:
                    return f'{ss}-{ee}'
            # 若不命中模板，回落为实际时段
            return f'{s}-{e}'

        # 构造 rows: 每位老师为一行，包含 slots
        rows_map = defaultdict(lambda: defaultdict(list))  # teacher_id -> (date-> list of cells)
        teacher_names = {}
        for l in lessons:
            t_id = l.teacher_id or 0
            t_name = getattr(l.teacher, 'username', '未指派')
            teacher_names[t_id] = t_name
            slot = _bucket_key(l.class_group.course_mode, l.start_time, l.end_time)
            rows_map[t_id][str(l.date)].append({
                "lesson_id": l.id,
                "class_group_id": l.class_group_id,
                "class_group_name": l.class_group.name,
                "subject": l.class_group.subject.name,
                "course_mode": l.class_group.course_mode,
                "slot": slot,
            })

        rows = []
        for t_id, day_map in rows_map.items():
            rows.append({
                "teacher_id": t_id,
                "teacher_name": teacher_names.get(t_id, ''),
                "days": { d: day_map.get(d, []) for d in dates }
            })

        return ok({
            "dates": dates,
            "rows": rows,
            "pattern": cycle.pattern,
            "rest_weekday": cycle.rest_weekday
        })

# === 周期名册：查询/新增/删除 ===
class CycleRosterView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_id, class_group_id):
        track = request.query_params.get('track')
        qs = CycleRoster.objects.filter(cycle_id=cycle_id, class_group_id=class_group_id)
        if track: qs = qs.filter(track=track)
        return ok(CycleRosterSerializer(qs, many=True).data)

    def post(self, request, cycle_id, class_group_id):
        students = request.data.get('students') or []
        type_ = request.data.get('type') or 'normal'   # normal/trial
        track = request.data.get('track')
        if not isinstance(students, list) or not students:
            return err('students required', 400, 400)
        created = []
        with transaction.atomic():
            for sid in students:
                obj, _ = CycleRoster.objects.get_or_create(
                    cycle_id=cycle_id, class_group_id=class_group_id,
                    student_id=sid, track=track,
                    defaults={'type': type_, 'created_by': request.user}
                )
                created.append(obj.id)
        return ok({"created_ids": created}, 'saved')

    def delete(self, request, cycle_id, class_group_id):
        students = request.data.get('students') or []
        track = request.data.get('track')
        if not isinstance(students, list) or not students:
            return err('students required', 400, 400)
        qs = CycleRoster.objects.filter(cycle_id=cycle_id, class_group_id=class_group_id, student_id__in=students)
        if track: qs = qs.filter(track=track)
        n = qs.count()
        qs.delete()
        return ok({"deleted": n}, 'deleted')

# === 发布：把周期名册映射到具体日期 → LessonParticipant ===
class CyclePublishView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not require_manager(request.user):
            return err('permission denied', 403, 403)

        cycle = Cycle.objects.filter(pk=pk).first()
        if not cycle: return err('cycle not found', 404, 404)

        body = request.data or {}
        scope = body.get('scope', 'future_only')
        mode = body.get('mode', 'participants')  # 本期只实现 participants
        dry_run = bool(body.get('dry_run', True))
        # 映射：
        #   map: {"Mon":["2025-10-01"], "Fri":["2025-10-02", ...]}
        #   tracks: {"A": {...}, "B": {...}}  # 可选
        map_ = body.get('map') or {}
        tracks = body.get('tracks') or {}

        # 计算目标自然日集合（按 scope 过滤今天/之后）
        today = timezone.localdate()
        def _valid_date(s):
            try:
                d = date.fromisoformat(s)
                return d if (scope=='include_today' and d>=cycle.date_from) or (scope=='future_only' and d>=max(today, cycle.date_from)) else None
            except Exception:
                return None

        # 构造 源列(周几)→目标自然日 集合
        weekday_map = defaultdict(list)  # "Mon"..."Sun"
        for w, arr in (map_ or {}).items():
            for s in (arr or []):
                d = _valid_date(s)
                if d: weekday_map[w].append(d)

        # tracks 覆盖（暑/寒）
        tracks_map = {}
        for trk, m in (tracks or {}).items():
            mm = defaultdict(list)
            for w, arr in (m or {}).items():
                for s in (arr or []):
                    d = _valid_date(s)
                    if d: mm[w].append(d)
            tracks_map[trk] = mm

        # 拉出本周期相关 roster
        rosters = list(CycleRoster.objects.filter(cycle=cycle)
                       .select_related('class_group','student'))

        # 目标：生成 (lesson_id, student_id, roster_id) 列表
        added, removed, missing = [], [], []

        # 预先拉出目标区间内的 lesson（按校区过滤）
        def _in_campus(lesson):
            c = lesson.room.campus_id if (lesson.room and lesson.room.campus_id) else (
                lesson.class_group.room_default.campus_id if (lesson.class_group and lesson.class_group.room_default and lesson.class_group.room_default.campus_id) else None
            )
            return c == cycle.campus_id

        # 目标日全集（用于一次性拉 lesson 做匹配）
        all_target_dates = set()
        for arr in weekday_map.values(): all_target_dates.update(arr)
        for mm in tracks_map.values():
            for arr in mm.values(): all_target_dates.update(arr)

        lessons_qs = Lesson.objects.filter(
            date__in=list(all_target_dates),
            status='scheduled'
        ).select_related('class_group','room','class_group__room_default')
        lessons = [l for l in lessons_qs if _in_campus(l)]

        # 索引：班级+日期 → lesson 列表（一个日期可能多节不同时间档）
        by_cg_date = defaultdict(list)
        for l in lessons:
            by_cg_date[(l.class_group_id, l.date)].append(l)

        # 周几工具
        def _weekday_name(d: date):
            # 与前端约定：Mon,Tue,Wed,Thu,Fri,Sat,Sun
            return ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][d.weekday()]

        # 现存由本周期发布产生的明细（用于差异删除）
        existing_items = {(it.lesson_id, it.student_id): it
                          for it in CyclePublishItem.objects.filter(cycle=cycle)}

        # 目标集：本次应存在的 (lesson_id, student_id) 集合
        target_pairs = set()

        # 组装目标
        for r in rosters:
            # 选择映射表：有 track 用 tracks_map[track]，否则 weekday_map
            use_map = tracks_map.get(r.track) if r.track in tracks_map else weekday_map

            # 周期的“源列”= 周一~周日。我们以“周几 → 目标自然日”一一映射
            # 遍历目标自然日集合，挑选同一 weekday 源列的映射
            # 注意：这里不强制 1→1，允许 1→多（你已确认）
            for w, target_dates in use_map.items():
                for d0 in target_dates:
                    # 找到该班级在 d0 的所有 lesson
                    ls = by_cg_date.get((r.class_group_id, d0), [])
                    if not ls:
                        missing.append({'date': str(d0), 'class_group_id': r.class_group_id})
                        continue
                    for l in ls:
                        target_pairs.add((l.id, r.student_id))

        # 差异：need_add / need_remove（仅针对本周期创建过的）
        existing_pairs = set(existing_items.keys())
        need_add = target_pairs - existing_pairs
        need_remove = existing_pairs - target_pairs  # 仅删“本周期生成的”，不会动手工/其它周期

        # dry-run 直接返回
        if dry_run:
            stats = {
                'add': len(need_add),
                'remove': len(need_remove),
                'missing_lessons': missing,
            }
            # 记录一次预演日志（可选）
            log = CyclePublishLog.objects.create(
                cycle=cycle, scope=scope, mode=mode, payload={'map': map_, 'tracks': tracks},
                diff_stats=stats, published_by=request.user
            )
            return ok({'log_id': log.id, **stats}, 'dry-run')

        # 执行
        with transaction.atomic():
            # 新增
            for (lesson_id, student_id) in need_add:
                # 查 roster（用于反查 type/track）
                r = next((x for x in rosters if x.student_id == student_id and
                          any(lesson_id in [ll.id for ll in by_cg_date.get((x.class_group_id, d), [])]
                              for dlist in (weekday_map.values() if x.track not in tracks_map else tracks_map[x.track].values())
                              for d in dlist)), None)
                r_type = r.type if r else CycleRoster.TYPE_NORMAL
                lp_type = LessonParticipant.TYPE_TRIAL if r_type == CycleRoster.TYPE_TRIAL else LessonParticipant.TYPE_TEMP

                # 幂等创建 participant
                lp, _ = LessonParticipant.objects.get_or_create(
                    lesson_id=lesson_id, student_id=student_id,
                    defaults={'type': lp_type, 'created_by': request.user}
                )
                # 记录发布明细
                CyclePublishItem.objects.create(
                    cycle=cycle, roster=r, lesson_id=lesson_id, student_id=student_id,
                    participant=lp, type=r_type, track=(r.track if r else None)
                )
                added.append({'lesson_id': lesson_id, 'student_id': student_id})

            # 删除（只删本周期生成的明细）
            for (lesson_id, student_id) in need_remove:
                item = existing_items.get((lesson_id, student_id))
                if item and item.participant_id:
                    # 仅当 participant 仍存在且没有被其它周期/手工引用（我们只记录一条）
                    LessonParticipant.objects.filter(id=item.participant_id).delete()
                if item:
                    item.delete()
                removed.append({'lesson_id': lesson_id, 'student_id': student_id})

            stats = {
                'add': len(added),
                'remove': len(removed),
                'missing_lessons': missing,
            }
            CyclePublishLog.objects.create(
                cycle=cycle, scope=scope, mode=mode, payload={'map': map_, 'tracks': tracks},
                diff_stats=stats, published_by=request.user
            )

        return ok({'added': added, 'removed': removed, 'missing_lessons': missing}, 'published')

class CycleMasterRosterView(APIView):
    """
    GET /api/schedule/cycle-schedule/cycles/{cycle_id}/roster
    聚合该周期下所有班级名册，支持筛选与分页。
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, cycle_id):
        # 可选：校验周期是否存在
        if not Cycle.objects.filter(pk=cycle_id).exists():
            return err('cycle not found', 404, 404)

        q = request.query_params

        # 基础查询
        qs = (CycleRoster.objects
              .filter(cycle_id=cycle_id)
              .select_related(
                  'class_group',
                  'class_group__subject',
                  'class_group__teacher_main',
                  'student'
              ))

        # 过滤项
        if q.get('class_group'):
            qs = qs.filter(class_group_id=q.get('class_group'))
        if q.get('subject'):
            qs = qs.filter(class_group__subject_id=q.get('subject'))
        if q.get('teacher'):
            qs = qs.filter(class_group__teacher_main_id=q.get('teacher'))
        if q.get('course_mode'):
            qs = qs.filter(class_group__course_mode=q.get('course_mode'))
        if q.get('grade'):
            qs = qs.filter(class_group__grade=q.get('grade'))
        if q.get('track'):
            qs = qs.filter(track=q.get('track'))
        if q.get('type'):
            qs = qs.filter(type=q.get('type'))
        if q.get('q'):
            qs = qs.filter(student__name__icontains=q.get('q'))

        # 排序（班级 → 学生名）
        qs = qs.order_by('class_group_id', 'student__name', 'id')

        # 分页
        try:
            page = max(1, int(q.get('page', 1)))
        except Exception:
            page = 1
        try:
            page_size = max(1, min(100, int(q.get('page_size', 20))))
        except Exception:
            page_size = 20

        total = qs.count()
        start = (page - 1) * page_size
        rows = qs[start:start + page_size]

        # 组装
        results = []
        for r in rows:
            cg = r.class_group
            subj = cg.subject
            t = cg.teacher_main
            results.append({
                'roster_id': r.id,
                'cycle_id': r.cycle_id,
                'class_group_id': cg.id,
                'class_group_name': cg.name or '',
                'subject_id': subj.id,
                'subject_name': subj.name,
                'course_mode': cg.course_mode,
                'grade': cg.grade,
                'track': r.track,
                'type': r.type,
                'student_id': r.student_id,
                'student_name': r.student.name,
                'teacher_id': (t.id if t else None),
                'teacher_name': ((getattr(t, 'name', None) or getattr(t, 'username', None)) if t else None),
            })

        # 若使用序列化器（可选）
        # ser = CycleMasterRosterItemSerializer(results, many=True)
        # return ok({'count': total, 'page': page, 'page_size': page_size, 'results': ser.data})

        # 直接返回
        return ok({'count': total, 'page': page, 'page_size': page_size, 'results': results})

def ok(data=None, message='OK', code=0, http=200):
    return Response({'code': code, 'message': message, 'data': data}, status=http)

def err(message='error', code=400, http=400, data=None):
    return Response({'code': code, 'message': message, 'data': data}, status=http)

class PreplanSlotListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """
        GET /api/schedule/cycle-schedule/preplan/slots?cycle=1&weekday=5
        """
        qs = CyclePreplanSlot.objects.all().select_related('class_group','class_group__subject','teacher_override','room_override')
        cycle = request.query_params.get('cycle')
        if cycle: qs = qs.filter(cycle_id=cycle)
        wd = request.query_params.get('weekday')
        if wd: qs = qs.filter(weekday=wd)
        cg = request.query_params.get('class_group')
        if cg: qs = qs.filter(class_group_id=cg)
        data = CyclePreplanSlotSerializer(qs.order_by('weekday','start_time','id'), many=True).data
        return ok(data)

    @transaction.atomic
    def post(self, request):
        """
        POST /api/schedule/cycle-schedule/preplan/slots
        body: {cycle, class_group, weekday, start_time, end_time, [teacher_override], [room_override], [note]}
        """
        ser = CyclePreplanSlotSerializer(data=request.data, context={'request': request})
        if ser.is_valid():
            obj = ser.save()
            return ok(CyclePreplanSlotSerializer(obj).data, 'created', http=201)
        return err(ser.errors, 400, 400)

class PreplanSlotDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        """
        PATCH /api/schedule/cycle-schedule/preplan/slots/{id}
        body: 任意字段的部分更新（可用于改时间、改老师/教室）
        """
        obj = CyclePreplanSlot.objects.filter(pk=pk).first()
        if not obj: return err('not found', 404, 404)
        ser = CyclePreplanSlotSerializer(obj, data=request.data, partial=True, context={'request': request})
        if ser.is_valid():
            obj = ser.save()
            return ok(CyclePreplanSlotSerializer(obj).data, 'updated')
        return err(ser.errors, 400, 400)

    def delete(self, request, pk):
        """
        DELETE /api/schedule/cycle-schedule/preplan/slots/{id}
        """
        obj = CyclePreplanSlot.objects.filter(pk=pk).first()
        if not obj: return err('not found', 404, 404)
        obj.delete()
        return ok({'deleted': 1}, 'deleted')