from django.shortcuts import render
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet
from .models import Group, GroupMember
from .serializers import GroupSerializer, GroupMemberSerializer

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
        user = get_object_or_404(settings.AUTH_USER_MODEL, id=user_id)
        
        group.add_member(user)
        return Response(
            {'message': f'Successfully added {user.email} to the group'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def remove_member(self, request, pk=None):
        """Remove a member from the group."""
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
        user = get_object_or_404(settings.AUTH_USER_MODEL, id=user_id)
        
        group.remove_member(user)
        return Response(
            {'message': f'Successfully removed {user.email} from the group'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='user-groups')
    def user_groups(self, request):
        """Get all groups the current user is a member of."""
        user = request.user
        groups = Group.objects.filter(members=user).prefetch_related('members', 'memberships')
        serializer = self.get_serializer(groups, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='user-groups-info')
    def user_groups_info(self, request):
        """Get all groups the current user is a member of with their information."""
        user = request.user
        groups = Group.objects.filter(members=user).prefetch_related('members', 'memberships')
        serializer = self.get_serializer(groups, many=True)
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
