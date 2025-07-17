from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Group, GroupMember

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'name']
    
    def get_name(self, obj):
        return obj.get_full_name() or obj.email.split('@')[0]

class GroupMemberSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = GroupMember
        fields = ['id', 'user', 'role', 'status', 'balance', 'joined_at']

class GroupSerializer(serializers.ModelSerializer):
    members = GroupMemberSerializer(many=True, read_only=True)
    admin = UserSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)

    class Meta:
        model = Group
        fields = [
            'id', 'name', 'description', 'created_by', 'created_at', 'updated_at',
            'status', 'currency', 'admin', 'members', 'join_code'
        ]
        read_only_fields = ['join_code', 'created_at', 'updated_at']
