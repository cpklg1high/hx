from decimal import Decimal, ROUND_HALF_UP
from rest_framework import serializers
from students.models import Student
from academics.models import Enrollment
from .models import PriceRule, GiftRule, PurchaseOrder, UNIT_OF_MODE

D = Decimal

def pick_price_rule(grade: int, course_mode: str, qty: D):
    """
    取价：同(年级, 班型)下，按 min_qty 从高到低匹配
    """
    qs = PriceRule.objects.filter(grade=grade, course_mode=course_mode, is_active=True).order_by('-min_qty')
    for r in qs:
        if D(qty) >= r.min_qty:
            return r
    return qs.last()  # 若都不满足，取最小档；若整体为空，则为 None

def pick_gift_rule_for_small_class(qty_sessions: int):
    qs = GiftRule.objects.filter(course_mode='small_class', is_active=True).order_by('-min_qty_sessions')
    for r in qs:
        if int(qty_sessions) >= r.min_qty_sessions:
            return r
    return None

class PriceIn(serializers.Serializer):
    student_id = serializers.IntegerField()
    course_mode = serializers.ChoiceField(choices=list(UNIT_OF_MODE.keys()))
    qty = serializers.DecimalField(max_digits=7, decimal_places=2, required=False)

    def validate(self, attrs):
        try:
            student = Student.objects.get(id=attrs['student_id'])
        except Student.DoesNotExist:
            raise serializers.ValidationError('学生不存在')
        attrs['student'] = student
        return attrs

    def create(self, v):
        student = v['student']
        course_mode = v['course_mode']
        qty = v.get('qty') or D('1')
        rule = pick_price_rule(student.grade, course_mode, qty)
        if not rule:
            raise serializers.ValidationError('未配置该年级与班型的价格规则')
        unit = UNIT_OF_MODE[course_mode]
        return {'unit': unit, 'unit_price': rule.unit_price, 'rule_id': rule.id}

class PriceOut(serializers.Serializer):
    unit = serializers.CharField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    rule_id = serializers.IntegerField()

class PurchaseIn(serializers.Serializer):
    student_id = serializers.IntegerField()
    course_mode = serializers.ChoiceField(choices=list(UNIT_OF_MODE.keys()))
    qty = serializers.DecimalField(max_digits=7, decimal_places=2)
    discount_percent = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, default=D('0'))
    direct_off = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, default=D('0'))
    remark = serializers.CharField(required=False, allow_blank=True, max_length=500)
    payment_method = serializers.CharField(required=False, allow_blank=True, max_length=20)
    paid_at = serializers.DateTimeField(required=False, allow_null=True)

    # 可选：人工覆盖赠送
    gift_override = serializers.DecimalField(max_digits=7, decimal_places=2, required=False, allow_null=True)
    gift_reason = serializers.CharField(required=False, allow_blank=True, max_length=200)

    def validate(self, attrs):
        # 学生
        try:
            student = Student.objects.get(id=attrs['student_id'])
        except Student.DoesNotExist:
            raise serializers.ValidationError('学生不存在')
        attrs['student'] = student

        # 数量
        qty = D(attrs['qty'])
        if qty <= 0:
            raise serializers.ValidationError('购买数量必须大于 0')

        course_mode = attrs['course_mode']
        unit = UNIT_OF_MODE[course_mode]
        attrs['unit'] = unit

        # 小班：购买数量必须为整数节
        if course_mode == 'small_class':
            if qty != qty.to_integral_value():
                raise serializers.ValidationError('小班购买数量必须为整数节')
        else:
            # 小时类：按 0.5 步长
            if (qty * D('2')) != (qty * D('2')).to_integral_value():
                raise serializers.ValidationError('小时购买数量必须以 0.5 为步长')

        # 金额校验
        dp = D(attrs.get('discount_percent') or 0)
        if dp < 0 or dp > 100:
            raise serializers.ValidationError('折扣必须在 0~100 之间')
        direct_off = D(attrs.get('direct_off') or 0)
        if direct_off < 0:
            raise serializers.ValidationError('立减金额不可为负')

        # 取价
        rule = pick_price_rule(student.grade, course_mode, qty)
        if not rule:
            raise serializers.ValidationError('未配置该年级与班型的价格规则')

        unit_price = D(rule.unit_price)
        subtotal = (qty * unit_price).quantize(D('0.01'), rounding=ROUND_HALF_UP)
        after_discount = (subtotal * (D('100') - dp) / D('100')).quantize(D('0.01'), rounding=ROUND_HALF_UP)
        if direct_off > after_discount:
            raise serializers.ValidationError('立减金额不能超过折扣后的小计金额')
        total_payable = (after_discount - direct_off).quantize(D('0.01'), rounding=ROUND_HALF_UP)

        # 赠送（小班自动、小时类默认 0）
        gift_qty = D('0')
        gift_rule = None
        gift_source = 'auto'
        if course_mode == 'small_class':
            gr = pick_gift_rule_for_small_class(int(qty))
            if gr:
                gift_rule = gr
                gift_qty = D(gr.gift_sessions)

        # 人工覆盖（可选）
        if 'gift_override' in attrs and attrs['gift_override'] is not None:
            gift_qty = D(attrs['gift_override'])
            if gift_qty < 0:
                raise serializers.ValidationError('赠送数量不可为负')
            gift_source = 'manual'

        attrs.update({
            'rule': rule,
            'unit_price': unit_price,
            'subtotal': subtotal,
            'total_payable': total_payable,
            'gift_qty': gift_qty,
            'gift_rule': gift_rule,
            'gift_source': gift_source,
        })
        return attrs

    def create(self, v):
        from django.db import transaction
        student = v['student']
        course_mode = v['course_mode']
        unit = v['unit']
        qty = D(v['qty'])
        gift_qty = D(v['gift_qty'])

        with transaction.atomic():
            po = PurchaseOrder.objects.create(
                student=student,
                course_mode=course_mode,
                unit=unit,
                qty=qty,
                gift_qty=gift_qty,
                unit_price=v['unit_price'],
                subtotal=v['subtotal'],
                discount_percent=v.get('discount_percent') or 0,
                direct_off=v.get('direct_off') or 0,
                total_payable=v['total_payable'],
                grade_snapshot=student.grade,
                price_rule_id=v['rule'].id,
                gift_rule_id=getattr(v.get('gift_rule'), 'id', None),
                gift_source=v.get('gift_source', 'auto'),
                payment_method=v.get('payment_method'),
                paid_at=v.get('paid_at'),
                transaction_no=v.get('transaction_no'),
                remark=v.get('remark') or '',
                operator=getattr(self.context.get('request'), 'user', None),
            )

            # 账户：学生 × 班型（唯一）
            en, _ = Enrollment.objects.get_or_create(
                student_id=student.id,
                course_mode=course_mode,
                defaults={'deduct_unit': unit, 'status': 'active'}
            )
            # 保持单位一致
            en.deduct_unit = unit

            if unit == 'hours':
                en.purchased_hours = (en.purchased_hours or 0) + qty
                en.remaining_hours = (en.remaining_hours or 0) + qty
                en.remaining_hours_gift = (getattr(en, 'remaining_hours_gift', 0) or 0) + gift_qty
            else:
                en.purchased_sessions = (en.purchased_sessions or 0) + int(qty)
                en.remaining_sessions = (en.remaining_sessions or 0) + int(qty)
                en.remaining_sessions_gift = (getattr(en, 'remaining_sessions_gift', 0) or 0) + int(gift_qty)

            # 仅累计实付金额
            en.amount_total = (en.amount_total or D('0')) + v['total_payable']
            en.save()

        return po

class PurchaseOut(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.name', read_only=True)
    operator_name = serializers.SerializerMethodField(read_only=True)

    def get_operator_name(self, obj):
        u = getattr(obj, 'operator', None)
        if not u:
            return None
        # 优先使用 name，其次 username
        return getattr(u, 'name', None) or getattr(u, 'username', None)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id','student','student_name','course_mode','unit','qty','gift_qty','unit_price','subtotal',
            'discount_percent','direct_off','total_payable','grade_snapshot','price_rule_id','gift_rule_id','gift_source',
            'payment_method','paid_at','transaction_no','need_invoice','invoice_title','tax_no','invoice_amount','invoice_remark',
            'remark','created_at','operator_name'
        ]

