from django.urls import path
from .views import PriceView, PurchaseCreateView , EnrollmentSummaryView, PurchaseListView

urlpatterns = [
    path('billing/price', PriceView.as_view()),
    path('billing/purchases', PurchaseCreateView.as_view()),
    path('billing/enrollment-summary', EnrollmentSummaryView.as_view()),  # GET 汇总
    path('billing/purchases/list', PurchaseListView.as_view()),      # GET 列表
]
