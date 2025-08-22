from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .serializers import PriceIn, PriceOut, PurchaseIn, PurchaseOut
from .models import PurchaseOrder, UNIT_OF_MODE
from django.db.models import Sum
from academics.models import Enrollment

ALLOWED_ROLES = ('admin', 'salesperson')

class PriceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        s = PriceIn(data=request.query_params)
        s.is_valid(raise_exception=True)
        data = s.save()
        return Response({'code': 200, 'data': PriceOut(data).data})

class PurchaseCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # 角色限制：先实现 admin/salesperson，后续再细化“只能给自己学生下单”
        if getattr(request.user, 'role', None) not in ALLOWED_ROLES:
            return Response({'code': 403, 'message': '无权限'}, status=status.HTTP_403_FORBIDDEN)

        s = PurchaseIn(data=request.data, context={'request': request})
        s.is_valid(raise_exception=True)
        po = s.save()
        return Response({'code': 200, 'message': '购买成功', 'data': PurchaseOut(po).data})

class EnrollmentSummaryView(APIView):
    """
    查询某学生各班型的账户汇总：付费剩余、赠送剩余、合计、累计实付、最近一笔购买
    GET /api/billing/enrollment-summary?student_id=1
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sid = request.query_params.get('student_id')
        if not sid:
            return Response({'code': 400, 'message': '缺少 student_id'}, status=400)

        # 在读账户（每个班型各一条）
        ens = Enrollment.objects.filter(student_id=sid, status='active').order_by('course_mode')
        data = []
        for en in ens:
            unit = en.deduct_unit  # hours / sessions
            # 付费与赠送剩余
            if unit == 'hours':
                remaining_paid = float(en.remaining_hours or 0)
                remaining_gift = float(getattr(en, 'remaining_hours_gift', 0) or 0)
                purchased_paid_qty = float(en.purchased_hours or 0)
            else:
                remaining_paid = int(en.remaining_sessions or 0)
                remaining_gift = int(getattr(en, 'remaining_sessions_gift', 0) or 0)
                purchased_paid_qty = int(en.purchased_sessions or 0)

            # 累计赠送总量（按订单礼赠汇总）
            gift_sum = PurchaseOrder.objects.filter(
                student_id=sid, course_mode=en.course_mode
            ).aggregate(s=Sum('gift_qty'))['s'] or 0

            # 最近一笔
            last_po = PurchaseOrder.objects.filter(student_id=sid, course_mode=en.course_mode).order_by('-id').first()
            last = None
            if last_po:
                # 取操作人显示名
                oper = getattr(last_po, 'operator', None)
                oper_name = None
                if oper:
                    oper_name = getattr(oper, 'name', None) or getattr(oper, 'username', None)

                last = {
                    'id': last_po.id,
                    'qty': str(last_po.qty),
                    'gift_qty': str(last_po.gift_qty),
                    'unit_price': str(last_po.unit_price),
                    'total_payable': str(last_po.total_payable),
                    'created_at': last_po.created_at,
                    'operator_name': oper_name,
                }

            data.append({
                'course_mode': en.course_mode,
                'unit': unit,
                'remaining_paid': remaining_paid,
                'remaining_gift': remaining_gift,
                'remaining_total': (remaining_paid + remaining_gift) if unit == 'hours' else (int(remaining_paid) + int(remaining_gift)),
                'purchased_paid_qty': purchased_paid_qty,
                'purchased_gift_qty': float(gift_sum) if unit == 'hours' else int(gift_sum),
                'amount_total': str(en.amount_total or 0),
                'last_purchase': last,
            })

        return Response({'code': 200, 'data': data})


class PurchaseListView(APIView):
    """
    查询某学生的购买记录（含赠送）
    GET /api/billing/purchases/list?student_id=1&page=1&page_size=20
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sid = request.query_params.get('student_id')
        if not sid:
            return Response({'code': 400, 'message': '缺少 student_id'}, status=400)

        try:
            page = int(request.query_params.get('page', 1))
            page_size = int(request.query_params.get('page_size', 20))
            page = max(page, 1); page_size = max(min(page_size, 100), 1)
        except Exception:
            page, page_size = 1, 20

        qs = PurchaseOrder.objects.filter(student_id=sid).order_by('-id')
        total = qs.count()
        items = qs[(page-1)*page_size : page*page_size]
        # 复用 PurchaseOut
        data = PurchaseOut(items, many=True).data

        return Response({'code': 200, 'data': {'results': data, 'count': total, 'page': page, 'page_size': page_size}})