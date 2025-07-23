from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import Settlement
from .serializers import SettlementSerializer
from groups.models import Group, GroupMember


class SettlementListCreateView(generics.ListCreateAPIView):
    """
    List all settlements for groups the user belongs to, or create a new settlement.
    """
    serializer_class = SettlementSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        # Get settlements where user is either sender or receiver
        return Settlement.objects.filter(
            Q(from_user=user) | Q(to_user=user)
        ).select_related('from_user', 'to_user', 'group')
    
    def perform_create(self, serializer):
        serializer.save()


class SettlementDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a settlement.
    """
    serializer_class = SettlementSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        # Get settlements where user is either sender or receiver
        return Settlement.objects.filter(
            Q(from_user=user) | Q(to_user=user)
        ).select_related('from_user', 'to_user', 'group')


class GroupSettlementListView(generics.ListAPIView):
    """
    List all settlements for a specific group.
    """
    serializer_class = SettlementSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        group_id = self.kwargs['group_id']
        user = self.request.user
        
        # Verify user is a member of the group
        group = get_object_or_404(Group, id=group_id)
        if not GroupMember.objects.filter(group=group, user=user).exists():
            return Settlement.objects.none()
        
        return Settlement.objects.filter(group=group).select_related(
            'from_user', 'to_user', 'group'
        )




