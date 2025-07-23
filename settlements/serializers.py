from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Settlement
from groups.models import Group, GroupMember

User = get_user_model()


class SettlementSerializer(serializers.ModelSerializer):
    from_user_email = serializers.EmailField(source='from_user.email', read_only=True)
    from_user_name = serializers.CharField(source='from_user.get_full_name', read_only=True)
    to_user_email = serializers.EmailField(source='to_user.email', read_only=True)
    to_user_name = serializers.CharField(source='to_user.get_full_name', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    class Meta:
        model = Settlement
        fields = [
            'id', 'from_user', 'from_user_email', 'from_user_name',
            'to_user', 'to_user_email', 'to_user_name',
            'group', 'group_name', 'amount', 'currency', 'settled_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Ensure both users are members of the group if group is specified"""
        if data.get('group'):
            group = data['group']
            from_user = data['from_user']
            to_user = data['to_user']
            
            if not GroupMember.objects.filter(group=group, user=from_user).exists():
                raise serializers.ValidationError("The settling user is not a member of this group.")
            
            if not GroupMember.objects.filter(group=group, user=to_user).exists():
                raise serializers.ValidationError("The receiving user is not a member of this group.")
        
        if data['from_user'] == data['to_user']:
            raise serializers.ValidationError("You cannot settle with yourself.")
        
        return data
    
    def create(self, validated_data):
        from groups.models import Transaction
        
        # Create the settlement
        settlement = Settlement.objects.create(**validated_data)
        
        # Create corresponding Transaction record if group is specified
        if settlement.group:
            transaction = Transaction.objects.create(
                group=settlement.group,
                description=f"Settlement: {settlement.from_user.get_full_name()} settled {settlement.amount} {settlement.currency} with {settlement.to_user.get_full_name()}",
                amount=settlement.amount,
                payer=settlement.from_user,
                category='settlement',
                date=settlement.settled_at,
                status='settled'  # Settlements are immediately settled
            )
            
            # Add participants to the transaction (from_user and to_user)
            transaction.participants.set([settlement.from_user, settlement.to_user])
        
        return settlement
