# backend/billing/management/commands/seed_pricing.py
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal
from billing.models import PriceRule, GiftRule
from students.models import Student, GRADE_CHOICES


# ===== 价格表（单位：元）=====
# 说明：
# - 一对一 / 一对二：三档（0-80, 81-160, 161+）对应 min_qty=0 / 81 / 161
# - 小班：按“元/次(节)”固定价，不分梯度（min_qty=0）
# - 年级ID来自 students.models.Student.GRADE_CHOICES:
#   1:一年级, 2:二年级, 3:三年级, 4:四年级, 5:五年级, 6:预初,
#   7:初一, 8:初二, 9:初三, 10:高一, 11:高二, 12:高三

def _tier(a, b, c):
    return (Decimal(a), Decimal(b), Decimal(c))

ONE_TO_ONE = {
    1: _tier(310, 290, 270),
    2: _tier(310, 290, 270),
    3: _tier(310, 290, 270),
    4: _tier(320, 300, 280),
    5: _tier(320, 300, 280),
    6: _tier(340, 320, 300),  # 预初
    7: _tier(350, 330, 310),
    8: _tier(360, 340, 320),
    9: _tier(375, 355, 335),
    10: _tier(400, 380, 360),
    11: _tier(410, 390, 370),
    12: _tier(430, 410, 390),
}

ONE_TO_TWO = {
    1: _tier(270, 250, 230),
    2: _tier(270, 250, 230),
    3: _tier(270, 250, 230),
    4: _tier(275, 255, 235),
    5: _tier(275, 255, 235),
    6: _tier(290, 270, 250),  # 预初
    7: _tier(295, 275, 255),
    8: _tier(305, 285, 265),
    9: _tier(320, 300, 280),
    10: _tier(330, 310, 290),
    11: _tier(340, 320, 300),
    12: _tier(350, 330, 310),
}

SMALL_CLASS_PER_SESSION = {
    1: Decimal(235), 2: Decimal(235), 3: Decimal(235),
    4: Decimal(245), 5: Decimal(245),
    6: Decimal(255),
    7: Decimal(265),
    8: Decimal(275),
    9: Decimal(285),
    10: Decimal(295),
    11: Decimal(305),
    12: Decimal(325),
}

# 小班赠送规则：购买 ≥ N 节，赠送 M 节
GIFT_RULES = [
    (40, 1), (60, 3), (80, 6), (100, 10), (140, 18), (180, 28), (220, 40)
]

TIERS_MIN_QTY = (0, 81, 161)

def _upsert_pricerule(grade: int, course_mode: str, min_qty: Decimal, unit_price: Decimal):
    obj, created = PriceRule.objects.get_or_create(
        grade=grade, course_mode=course_mode, min_qty=min_qty,
        defaults={'unit_price': unit_price, 'is_active': True}
    )
    updated = False
    if not created:
        # 若价格不同则更新；始终确保 is_active=True
        if obj.unit_price != unit_price or obj.is_active is False:
            obj.unit_price = unit_price
            obj.is_active = True
            obj.save(update_fields=['unit_price', 'is_active'])
            updated = True
    return created, updated

def _upsert_giftrule(min_qty_sessions: int, gift_sessions: int):
    obj, created = GiftRule.objects.get_or_create(
        course_mode='small_class',
        min_qty_sessions=min_qty_sessions,
        defaults={'gift_sessions': gift_sessions, 'is_active': True}
    )
    updated = False
    if not created and (obj.gift_sessions != gift_sessions or obj.is_active is False):
        obj.gift_sessions = gift_sessions
        obj.is_active = True
        obj.save(update_fields=['gift_sessions', 'is_active'])
        updated = True
    return created, updated


class Command(BaseCommand):
    help = "批量导入/更新价格规则与小班赠送规则。默认 dry-run，仅打印；加 --apply 才实际写入。可用 --reset 先清空再导入。"

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='实际写入数据库（默认只打印预览）')
        parser.add_argument('--reset', action='store_true', help='导入前清空 PriceRule/GiftRule 表（谨慎使用）')

    @transaction.atomic
    def handle(self, *args, **options):
        apply = options.get('apply', False)
        do_reset = options.get('reset', False)

        # 检查年级枚举是否存在
        if not GRADE_CHOICES:
            raise CommandError("无法读取 students.models.GRADE_CHOICES，请确认 students.models 定义。")

        # 预览/清空
        if do_reset:
            msg = "即将清空 PriceRule/GiftRule 后重新导入。"
            if apply:
                PriceRule.objects.all().delete()
                GiftRule.objects.all().delete()
                self.stdout.write(self.style.WARNING("已清空 PriceRule 与 GiftRule。"))
            else:
                self.stdout.write(self.style.WARNING("[dry-run] " + msg))

        created_cnt = updated_cnt = 0

        # 一对一
        for grade, (p0, p1, p2) in ONE_TO_ONE.items():
            for min_qty, price in zip(TIERS_MIN_QTY, (p0, p1, p2)):
                if apply:
                    c, u = _upsert_pricerule(grade, 'one_to_one', Decimal(min_qty), price)
                    created_cnt += int(c); updated_cnt += int(u)
                self.stdout.write(f"[one_to_one] grade={grade} min>={min_qty} price={price} {'(write)' if apply else ''}")

        # 一对二
        for grade, (p0, p1, p2) in ONE_TO_TWO.items():
            for min_qty, price in zip(TIERS_MIN_QTY, (p0, p1, p2)):
                if apply:
                    c, u = _upsert_pricerule(grade, 'one_to_two', Decimal(min_qty), price)
                    created_cnt += int(c); updated_cnt += int(u)
                self.stdout.write(f"[one_to_two] grade={grade} min>={min_qty} price={price} {'(write)' if apply else ''}")

        # 小班
        for grade, price in SMALL_CLASS_PER_SESSION.items():
            if apply:
                c, u = _upsert_pricerule(grade, 'small_class', Decimal(0), price)
                created_cnt += int(c); updated_cnt += int(u)
            self.stdout.write(f"[small_class] grade={grade} min>=0 price={price} {'(write)' if apply else ''}")

        # 赠送
        for min_qty, gift in GIFT_RULES:
            if apply:
                c, u = _upsert_giftrule(int(min_qty), int(gift))
                created_cnt += int(c); updated_cnt += int(u)
            self.stdout.write(f"[gift] small_class buy>={min_qty} → gift={gift} {'(write)' if apply else ''}")

        self.stdout.write(self.style.SUCCESS(
            f"完成：created={created_cnt}, updated={updated_cnt}, mode={'APPLY' if apply else 'DRY-RUN'}"
        ))
