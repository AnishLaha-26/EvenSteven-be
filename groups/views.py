from django.shortcuts import render
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet
from .models import Group, GroupMember, Transaction
from .serializers import GroupSerializer, GroupMemberSerializer, TransactionSerializer
from .balance_manager import BalanceManager
from .balance_serializers import (
    GroupBalanceSummarySerializer,
    GroupBalanceSummaryFromUserPerspectiveSerializer,
    MemberBalanceDetailSerializer,
    BalanceUpdateSerializer
)

User = get_user_model()

# Create your views here.

class GroupViewSet(mixins.CreateModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  mixins.ListModelMixin,
                  GenericViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return groups where the user is a member."""
        # For debugging, return all groups
        return Group.objects.all()

    def create(self, request, *args, **kwargs):
        """Create a new group with the current user as admin."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create the group
        group = serializer.save(created_by=request.user)
        
        # Automatically add the creator as admin
        group.add_member(request.user, role='admin')
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    @action(detail=True, methods=['post'])
    def join(self, request, pk=None):
        """Join a group using join code."""
        group = self.get_object()
        join_code = request.data.get('join_code')
        
        if group.join_code != join_code:
            return Response(
                {'error': 'Invalid join code'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if GroupMember.objects.filter(user=request.user, group=group).exists():
            return Response(
                {'error': 'Already a member of this group'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        group.add_member(request.user)
        return Response(
            {'message': 'Successfully joined the group'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def add_member(self, request, pk=None):
        """Add a member to the group."""
        group = self.get_object()
        
        # Only admins can add members
        if not GroupMember.objects.filter(
            user=request.user,
            group=group,
            role='admin'
        ).exists():
            return Response(
                {'error': 'Only admins can add members'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        user_id = request.data.get('user_id')
        user = get_object_or_404(User, id=user_id)
        
        group.add_member(user)
        return Response(
            {'message': f'Successfully added {user.email} to the group'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        """Admin removes a member from the group."""
        group = self.get_object()
        
        # Only admins can remove members
        if not GroupMember.objects.filter(
            user=request.user,
            group=group,
            role='admin'
        ).exists():
            return Response(
                {'error': 'Only admins can remove members'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        user_id = request.data.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        user = get_object_or_404(User, id=user_id)
        
        # Check if user is actually a member of the group
        if not GroupMember.objects.filter(user=user, group=group).exists():
            return Response(
                {'error': 'User is not a member of this group'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        group.remove_member(user)
        return Response(
            {'message': f'Successfully removed {user.email} from the group'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def leave_group(self, request, pk=None):
        """Member leaves the group themselves."""
        group = self.get_object()
        user = request.user
        
        # Check if user is a member of the group
        membership = GroupMember.objects.filter(user=user, group=group).first()
        if not membership:
            return Response(
                {'error': 'You are not a member of this group'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is the only admin - prevent leaving if so
        admin_count = GroupMember.objects.filter(
            group=group, 
            role='admin',
            status='active'
        ).count()
        
        if membership.role == 'admin' and admin_count == 1:
            return Response(
                {'error': 'Cannot leave group as the only admin. Please assign another admin first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        group.remove_member(user)
        return Response(
            {'message': 'Successfully left the group'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['post'])
    def join_by_code(self, request):
        """Join a group using only the join code."""
        join_code = request.data.get('join_code')
        
        if not join_code:
            return Response(
                {'error': 'Join code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find group by join code
        try:
            group = Group.objects.get(join_code=join_code.strip())
        except Group.DoesNotExist:
            return Response(
                {'error': 'Invalid join code'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user is already a member
        if GroupMember.objects.filter(user=request.user, group=group, status='active').exists():
            return Response(
                {'error': 'Already a member of this group'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add user to group
        group.add_member(request.user)
        
        return Response(
            {
                'message': 'Successfully joined the group',
                'group': {
                    'id': group.id,
                    'name': group.name,
                    'description': group.description
                }
            },
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='user-groups')
    def user_groups(self, request):
        """Get all groups the current user is a member of."""
        user = request.user
        groups = Group.objects.filter(members=user).prefetch_related('memberships')
        serializer = self.get_serializer(groups, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='user-groups-info')
    def user_groups_info(self, request):
        """Get all groups the current user is a member of with their information."""
        user = request.user
        groups = Group.objects.filter(members=user).prefetch_related('memberships')
        serializer = self.get_serializer(groups, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'], url_path='recent-transactions')
    def recent_transactions(self, request, pk=None):
        """Get recent transactions for a specific group."""
        group = self.get_object()
        
        # Check if user is a member of the group
        if not GroupMember.objects.filter(user=request.user, group=group).exists():
            return Response(
                {'error': 'You are not a member of this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get recent transactions (limit to last 20)
        transactions = group.transactions.all()[:20]
        
        serializer = TransactionSerializer(transactions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='balance-summary')
    def balance_summary(self, request, pk=None):
        """Get balance summary for all members in the group from current user's perspective."""
        group = self.get_object()
        
        # Check if user is a member of the group
        if not GroupMember.objects.filter(user=request.user, group=group).exists():
            return Response(
                {'error': 'You are not a member of this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get balance summary from current user's perspective
        summary = BalanceManager.get_group_balance_summary_for_user(group, request.user)
        serializer = GroupBalanceSummaryFromUserPerspectiveSerializer(summary)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='my-balance')
    def my_balance(self, request, pk=None):
        """Get detailed balance information for the current user in the group."""
        group = self.get_object()
        
        # Check if user is a member of the group
        if not GroupMember.objects.filter(user=request.user, group=group).exists():
            return Response(
                {'error': 'You are not a member of this group'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get detailed balance for current user
        balance_details = BalanceManager.get_member_balance_details(group, request.user)
        if not balance_details:
            return Response(
                {'error': 'Balance information not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = MemberBalanceDetailSerializer(balance_details)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], url_path='update-balances')
    def update_balances(self, request, pk=None):
        """Update balances for all members in the group (admin only)."""
        group = self.get_object()
        
        # Check if user is an admin of the group
        if not GroupMember.objects.filter(
            user=request.user,
            group=group,
            role='admin'
        ).exists():
            return Response(
                {'error': 'Only admins can update group balances'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Update all balances
        updated_members = BalanceManager.update_all_group_balances(group)
        updated_user_ids = [member.user.id for member in updated_members]
        
        response_data = {
            'success': True,
            'message': f'Updated balances for {len(updated_members)} members',
            'updated_members': updated_user_ids
        }
        
        serializer = BalanceUpdateSerializer(response_data)
        return Response(serializer.data)

class GroupMemberViewSet(viewsets.ModelViewSet):
    queryset = GroupMember.objects.all()
    serializer_class = GroupMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Return group members for groups where the user is a member."""
        return GroupMember.objects.filter(
            group__members=self.request.user
        )
