from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from students.models import Student, GRADE_CHOICES  # 用于 grade choices 与外键

User = get_user_model()

# 固定三种班型
COURSE_MODE = (
    ('one_to_one', '一对一'),
    ('one_to_two', '一对二'),
    ('small_class', '小班'),
)

# 由班型推导扣课单位
UNIT_OF_MODE = {
    'one_to_one': 'hours',
    'one_to_two': 'hours',
    'small_class': 'sessions',
}

class PriceRule(models.Model):
    """
    价格规则：维度 = 年级 + 班型 + 阶梯(min_qty) -> 单价
    - 小班不分梯度时，可仅录一条 min_qty=0
    """
    grade = models.PositiveSmallIntegerField(choices=GRADE_CHOICES, db_index=True)
    course_mode = models.CharField(max_length=20, choices=COURSE_MODE, db_index=True)
    min_qty = models.DecimalField(max_digits=7, decimal_places=2, default=0)  # 起购数量（小时或节）
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)        # 元/小时 或 元/节
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'edu_price_rule'
        indexes = [models.Index(fields=['grade', 'course_mode', 'is_active'])]
        ordering = ['grade', 'course_mode', '-min_qty']

    def __str__(self):
        return f'PriceRule<{self.id}> grade={self.grade} mode={self.course_mode} min>={self.min_qty} price={self.unit_price}'


class GiftRule(models.Model):
    """
    小班赠送规则：购买≥N节，赠送M节
    仅对 course_mode='small_class' 生效
    """
    course_mode = models.CharField(max_length=20, choices=COURSE_MODE, default='small_class')
    min_qty_sessions = models.PositiveIntegerField()  # 购买≥N节
    gift_sessions = models.PositiveIntegerField()     # 赠送M节
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'edu_gift_rule'
        ordering = ['-min_qty_sessions']

    def __str__(self):
        return f'GiftRule<{self.id}> min>={self.min_qty_sessions} gift={self.gift_sessions}'


class PurchaseOrder(models.Model):
    """
    购买订单：一次结算锁定班型、单位、单价与规则快照
    - gift_qty 记录赠送数量（不计金额）
    - total_payable 仅计实付（先折扣%后立减¥）
    """
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='purchase_orders')
    course_mode = models.CharField(max_length=20, choices=COURSE_MODE, db_index=True)
    unit = models.CharField(max_length=16)  # 冗余快照：hours/sessions

    qty = models.DecimalField(max_digits=7, decimal_places=2)                         # 购买数量（小时/节）
    gift_qty = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal('0'))  # 赠送数量

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)                 # 单价（快照）
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)                   # 小计=qty*unit_price
    discount_percent = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0'))  # 0~100
    direct_off = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))       # 立减
    total_payable = models.DecimalField(max_digits=12, decimal_places=2)              # 实付

    # 规则快照
    grade_snapshot = models.PositiveSmallIntegerField(choices=GRADE_CHOICES)
    price_rule_id = models.IntegerField(null=True, blank=True)
    gift_rule_id = models.IntegerField(null=True, blank=True)
    gift_source = models.CharField(max_length=10, default='auto')  # auto/manual

    # 支付信息（先留字段）
    payment_method = models.CharField(max_length=20, null=True, blank=True)  # cash/alipay/wechat/bank_transfer
    paid_at = models.DateTimeField(null=True, blank=True)
    transaction_no = models.CharField(max_length=100, null=True, blank=True)

    # 发票信息（先留字段）
    need_invoice = models.BooleanField(default=False)
    invoice_title = models.CharField(max_length=200, null=True, blank=True)
    tax_no = models.CharField(max_length=50, null=True, blank=True)
    invoice_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    invoice_remark = models.CharField(max_length=500, null=True, blank=True)

    remark = models.CharField(max_length=500, blank=True, default='')
    operator = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'edu_purchase_order'
        ordering = ['-id']
        indexes = [models.Index(fields=['student', 'created_at'])]

    def __str__(self):
        return f'PurchaseOrder<{self.id}> S{self.student_id} mode={self.course_mode} qty={self.qty}+gift{self.gift_qty} total={self.total_payable}'
