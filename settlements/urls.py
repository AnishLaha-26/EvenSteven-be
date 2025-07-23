from django.urls import path
from . import views

app_name = 'settlements'

urlpatterns = [
    # List and create settlements
    path('', views.SettlementListCreateView.as_view(), name='settlement-list'),
    
    # Get, update, delete specific settlement
    path('<int:pk>/', views.SettlementDetailView.as_view(), name='settlement-detail'),
    
    # List settlements for a specific group
    path('group/<int:group_id>/', views.GroupSettlementListView.as_view(), name='group-settlements'),
]
