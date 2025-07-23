from django.urls import path
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'expenses'

router = DefaultRouter()

urlpatterns = [
    # List and create expenses
    path('', views.ExpenseListCreateView.as_view(), name='expense-list'),
    
    # Get, update, delete specific expense
    path('<int:pk>/', views.ExpenseDetailView.as_view(), name='expense-detail'),
    
    # List expenses for a specific group
    path('group/<int:group_id>/', views.GroupExpenseListView.as_view(), name='group-expenses'),
    
    # List and create payments
    path('payments/', views.PaymentListCreateView.as_view(), name='payment-list'),
    
    # Get, update, delete specific payment
    path('payments/<int:pk>/', views.PaymentDetailView.as_view(), name='payment-detail'),
    
    # List payments for a specific group
    path('payments/group/<int:group_id>/', views.GroupPaymentListView.as_view(), name='group-payments'),
    
    # User expense summary
    path('summary/', views.user_expense_summary, name='user-expense-summary'),
    
    # Payment statistics
    path('payments/statistics/', views.payment_statistics, name='payment-statistics'),
    
    # Group payment summary with settlement suggestions
    path('payments/group/<int:group_id>/summary/', views.group_payment_summary, name='group-payment-summary'),
]
