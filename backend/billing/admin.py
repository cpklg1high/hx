from django.contrib import admin
from .models import PriceRule, GiftRule, PurchaseOrder

@admin.register(PriceRule)
class PriceRuleAdmin(admin.ModelAdmin):
    list_display = ('id','grade','course_mode','min_qty','unit_price','is_active')
    list_filter = ('grade','course_mode','is_active')
    search_fields = ('course_mode',)
    ordering = ('grade','course_mode','-min_qty')

@admin.register(GiftRule)
class GiftRuleAdmin(admin.ModelAdmin):
    list_display = ('id','course_mode','min_qty_sessions','gift_sessions','is_active')
    list_filter = ('course_mode','is_active')
    ordering = ('-min_qty_sessions',)

@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('id','student','course_mode','unit','qty','gift_qty','unit_price','total_payable','created_at')
    list_filter = ('course_mode','unit','payment_method')
    search_fields = ('student__name',)
    ordering = ('-id',)
