from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings

from .models import Enrollment            # 来自 academics.models
from students.models import Student       # 学生模型在 students.models

class DevEnrollmentCreateView(APIView):
    """仅在 DEBUG=True 时可用，用来在开发环境快速造“在读学员”"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 生产环境禁止
        if not getattr(settings, 'DEBUG', False):
            return Response({'code': 403, 'message': 'Dev API only in DEBUG'}, status=403)

        data = request.data
        student_id = data.get('student_id')
        deduct_unit = data.get('deduct_unit')  # 'hours' or 'sessions'

        if deduct_unit not in ('hours', 'sessions'):
            return Response({'code': 400, 'message': 'deduct_unit must be hours or sessions'}, status=400)

        # 校验学生存在
        if not Student.objects.filter(id=student_id).exists():
            return Response({'code': 400, 'message': 'student not found'}, status=400)

        en = Enrollment.objects.create(
            student_id=student_id,
            deduct_unit=deduct_unit,
            purchased_hours=data.get('purchased_hours', 0) or 0,
            remaining_hours=data.get('remaining_hours', 0) or 0,
            purchased_sessions=data.get('purchased_sessions', 0) or 0,
            remaining_sessions=data.get('remaining_sessions', 0) or 0,
            status=data.get('status', 'active'),
            amount_total=data.get('amount_total', 0) or 0
        )
        return Response({'code': 200, 'data': {'id': en.id}})
