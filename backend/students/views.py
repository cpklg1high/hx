from rest_framework import viewsets, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.contrib.auth import get_user_model

from .models import (
    Student, School, GRADE_CHOICES, RELATION_CHOICES, VISIT_CHANNEL, ReferralReward
)
from .serializers import StudentListOut, StudentIn
from academics.models import Enrollment

User = get_user_model()

# ========= 字典 =========

class DictGradesView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        data = [{'id': k, 'name': v} for k, v in GRADE_CHOICES]
        return Response({'code': 200, 'data': data})

class DictRelationsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        data = [{'code': k, 'label': v} for k, v in RELATION_CHOICES]
        return Response({'code': 200, 'data': data})

class DictVisitChannelsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        data = [{'code': k, 'label': v} for k, v in VISIT_CHANNEL]
        return Response({'code': 200, 'data': data})

class SalespersonsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        kw = request.query_params.get('keyword', '')
        qs = User.objects.filter(role='salesperson')
        if kw:
            qs = qs.filter(Q(username__icontains=kw) | Q(name__icontains=kw))
        data = [{'id': u.id, 'name': u.name or u.username} for u in qs.order_by('id')[:30]]
        return Response({'code': 200, 'data': data})

# ========= 学校（按拼音排序 + 搜索） =========

class SchoolsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        kw = (request.query_params.get('keyword') or '').strip()
        qs = School.objects.filter(is_active=True)
        if kw:
            qs = qs.filter(Q(name__icontains=kw) | Q(pinyin__icontains=kw.lower()))
        qs = qs.order_by('pinyin', 'name')[:100]
        data = [{'id': s.id, 'name': s.name, 'pinyin': s.pinyin} for s in qs]
        return Response({'code': 200, 'data': data})

# ========= 在读学员搜索（仅返回在读） =========

class StudentsSearchView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        kw = request.query_params.get('keyword', '')
        qs = Student.objects.all()
        if kw:
            qs = qs.filter(Q(name__icontains=kw) | Q(remark__icontains=kw))
        # 仅保留在读
        ids = [s.id for s in qs[:200] if Enrollment.is_student_studying(s.id)]
        qs = Student.objects.filter(id__in=ids).order_by('-id')[:30]
        data = []
        for s in qs:
            link = s.guardian_links.filter(is_primary=True).select_related('guardian').first()
            primary = None
            if link:
                primary = {
                    'relation_label': dict(RELATION_CHOICES).get(link.relation_code, ''),
                    'phone_mask': link.guardian.phone if not link.guardian.phone else (link.guardian.phone[:3] + '****' + link.guardian.phone[-4:])
                }
            data.append({
                'id': s.id, 'name': s.name,
                'grade_label': dict(GRADE_CHOICES).get(s.grade, ''),
                'primary_contact': primary
            })
        return Response({'code': 200, 'data': data})

# ========= 学生 CRUD =========

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related('school', 'current_salesperson').all().order_by('-id')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ['list', 'retrieve']:
            return StudentListOut
        return StudentIn

    def list(self, request, *args, **kwargs):
        kw = request.query_params.get('keyword')
        grade_id = request.query_params.get('grade_id')
        salesperson_id = request.query_params.get('salesperson_id')
        academic_status = request.query_params.get('academic_status')
        school_id = request.query_params.get('school_id')

        qs = self.get_queryset()
        if kw:
            qs = qs.filter(Q(name__icontains=kw) | Q(remark__icontains=kw) | Q(school__name__icontains=kw))
        if grade_id:
            qs = qs.filter(grade=int(grade_id))
        if salesperson_id:
            qs = qs.filter(current_salesperson_id=int(salesperson_id))
        if academic_status:
            qs = qs.filter(academic_status=academic_status)
        if school_id:  # ← 新增
            qs = qs.filter(school_id=int(school_id))

        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        start = (page - 1) * page_size
        end = start + page_size
        total = qs.count()
        ser = StudentListOut(qs[start:end], many=True)
        return Response({'code': 200, 'data': {'results': ser.data, 'count': total}})

    def create(self, request, *args, **kwargs):
        ser = StudentIn(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        stu = ser.save()
        return Response({'code': 200, 'data': {'id': stu.id}})

    def update(self, request, *args, **kwargs):
        return Response({'code': 400, 'message': '编辑接口将在下一步提供'}, status=400)

# ========= 转介绍奖励查询（按新生ID） =========

class ReferralRewardByStudentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request, student_id: int):
        try:
            rr = (ReferralReward.objects
                  .select_related('referrer_student', 'new_student')
                  .get(new_student_id=student_id))
        except ReferralReward.DoesNotExist:
            return Response({'code': 404, 'message': 'No reward for this student'}, status=404)

        data = {
            'id': rr.id,
            'status': rr.status,
            'referrer_student': {'id': rr.referrer_student_id, 'name': rr.referrer_student.name},
            'new_student': {'id': rr.new_student_id, 'name': rr.new_student.name},
            'amount': str(rr.amount) if rr.amount is not None else None,
            'rule_snapshot': rr.get_rule_snapshot(),
            'created_at': rr.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        }
        return Response({'code': 200, 'data': data})
