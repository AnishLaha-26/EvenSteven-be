from rest_framework import serializers
from .models import Expense, ExpenseSplit, Payment
from groups.models import Group, GroupMember
from django.contrib.auth import get_user_model

User = get_user_model()


class ExpenseSplitSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    
    class Meta:
        model = ExpenseSplit
        fields = ['id', 'user', 'user_email', 'user_name', 'amount', 'percentage', 'created_at']
        read_only_fields = ['id', 'created_at']


class ExpenseSerializer(serializers.ModelSerializer):
    splits = ExpenseSplitSerializer(many=True, read_only=True)
    paid_by_email = serializers.EmailField(source='paid_by.email', read_only=True)
    paid_by_name = serializers.CharField(source='paid_by.get_full_name', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    # For creating expenses with splits
    split_users = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of user IDs to split the expense with"
    )
    split_equally = serializers.BooleanField(
        write_only=True,
        default=True,
        help_text="Whether to split the expense equally among users"
    )
    
    class Meta:
        model = Expense
        fields = [
            'id', 'group', 'paid_by', 'paid_by_email', 'paid_by_name',
            'group_name', 'amount', 'currency', 'description', 'date',
            'splits', 'split_users', 'split_equally', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_group(self, value):
        """Ensure the user is a member of the group"""
        user = self.context['request'].user
        if not GroupMember.objects.filter(group=value, user=user).exists():
            raise serializers.ValidationError("You are not a member of this group.")
        return value
    
    def validate_paid_by(self, value):
        """Ensure the paid_by user is a member of the group"""
        group = self.initial_data.get('group')
        if group and not GroupMember.objects.filter(group_id=group, user=value).exists():
            raise serializers.ValidationError("The paying user is not a member of this group.")
        return value
    
    def create(self, validated_data):
        from groups.models import Transaction
        
        split_users = validated_data.pop('split_users', [])
        split_equally = validated_data.pop('split_equally', True)
        
        # Create the expense
        expense = Expense.objects.create(**validated_data)
        
        # Create splits if split_users is provided
        if split_users:
            self._create_splits(expense, split_users, split_equally)
        else:
            # Default: split equally among all group members
            group_members = GroupMember.objects.filter(group=expense.group)
            member_ids = [member.user.id for member in group_members]
            self._create_splits(expense, member_ids, True)
        
        # Create corresponding Transaction record
        transaction = Transaction.objects.create(
            group=expense.group,
            description=expense.description,
            amount=expense.amount,
            payer=expense.paid_by,
            category='expense',
            date=expense.date,
            status='pending'
        )
        
        # Add participants to the transaction
        # Get all users who have splits for this expense
        split_user_ids = expense.splits.values_list('user_id', flat=True)
        transaction.participants.set(split_user_ids)
        
        return expense
    
    def _create_splits(self, expense, user_ids, split_equally):
        """Create expense splits for the given users"""
        if split_equally:
            split_amount = expense.amount / len(user_ids)
            percentage = 100.0 / len(user_ids)
        
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                # Verify user is a group member
                if GroupMember.objects.filter(group=expense.group, user=user).exists():
                    ExpenseSplit.objects.create(
                        expense=expense,
                        user=user,
                        amount=split_amount if split_equally else 0,
                        percentage=percentage if split_equally else None
                    )
            except User.DoesNotExist:
                continue


class PaymentSerializer(serializers.ModelSerializer):
    from_user_email = serializers.EmailField(source='from_user.email', read_only=True)
    from_user_name = serializers.CharField(source='from_user.get_full_name', read_only=True)
    to_user_email = serializers.EmailField(source='to_user.email', read_only=True)
    to_user_name = serializers.CharField(source='to_user.get_full_name', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)
    
    # Additional computed fields
    is_current_user_sender = serializers.SerializerMethodField()
    is_current_user_receiver = serializers.SerializerMethodField()
    formatted_amount = serializers.SerializerMethodField()
    days_ago = serializers.SerializerMethodField()
    
    # Write-only fields for creation
    to_user_email_input = serializers.EmailField(write_only=True, required=False, help_text="Email of recipient user")
    
    def get_is_current_user_sender(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.from_user == request.user
        return False
    
    def get_is_current_user_receiver(self, obj):
        request = self.context.get('request')
        if request and request.user:
            return obj.to_user == request.user
        return False
    
    def get_formatted_amount(self, obj):
        return f"{obj.amount} {obj.currency}"
    
    def get_days_ago(self, obj):
        from datetime import date
        today = date.today()
        delta = today - obj.payment_date
        return delta.days
    
    class Meta:
        model = Payment
        fields = [
            'id', 'from_user', 'from_user_email', 'from_user_name',
            'to_user', 'to_user_email', 'to_user_name', 'to_user_email_input',
            'group', 'group_name', 'amount', 'currency', 'description',
            'payment_date', 'created_at', 'updated_at',
            'is_current_user_sender', 'is_current_user_receiver',
            'formatted_amount', 'days_ago'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate_amount(self, value):
        """Validate payment amount"""
        if value <= 0:
            raise serializers.ValidationError("Payment amount must be greater than zero.")
        if value > 999999.99:
            raise serializers.ValidationError("Payment amount cannot exceed 999,999.99.")
        return value
    
    def validate_description(self, value):
        """Validate payment description"""
        if value and len(value.strip()) == 0:
            return None  # Convert empty strings to None
        return value
    
    def validate(self, data):
        """Ensure both users are members of the group if group is specified"""
        # Handle to_user_email_input for user lookup
        to_user_email = data.pop('to_user_email_input', None)
        if to_user_email and not data.get('to_user'):
            try:
                to_user = User.objects.get(email=to_user_email)
                data['to_user'] = to_user
            except User.DoesNotExist:
                raise serializers.ValidationError({"to_user_email_input": "User with this email does not exist."})
        
        # Validate group membership
        if data.get('group'):
            group = data['group']
            from_user = data.get('from_user') or self.context['request'].user
            to_user = data['to_user']
            
            if not GroupMember.objects.filter(group=group, user=from_user).exists():
                raise serializers.ValidationError({"group": "The paying user is not a member of this group."})
            
            if not GroupMember.objects.filter(group=group, user=to_user).exists():
                raise serializers.ValidationError({"to_user": "The receiving user is not a member of this group."})
        
        # Validate users are different
        from_user = data.get('from_user') or self.context['request'].user
        if from_user == data['to_user']:
            raise serializers.ValidationError({"to_user": "You cannot make a payment to yourself."})
        
        # Validate payment date is not in the future
        from datetime import date
        if data.get('payment_date') and data['payment_date'] > date.today():
            raise serializers.ValidationError({"payment_date": "Payment date cannot be in the future."})
        
        return data
    
    def create(self, validated_data):
        from groups.models import Transaction
        
        # Set from_user to current user if not specified
        if 'from_user' not in validated_data:
            validated_data['from_user'] = self.context['request'].user
        
        # Create the payment
        payment = Payment.objects.create(**validated_data)
        
        # Create corresponding Transaction record if group is specified
        if payment.group:
            try:
                transaction = Transaction.objects.create(
                    group=payment.group,
                    description=payment.description or f"Payment from {payment.from_user.get_full_name()} to {payment.to_user.get_full_name()}",
                    amount=payment.amount,
                    payer=payment.from_user,
                    category='payment',
                    date=payment.payment_date,
                    status='settled'  # Payments are immediately settled
                )
                
                # Add participants to the transaction (from_user and to_user)
                transaction.participants.set([payment.from_user, payment.to_user])
            except Exception as e:
                # Log the error but don't fail the payment creation
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to create transaction for payment {payment.id}: {str(e)}")
        
        return payment
    
    def update(self, instance, validated_data):
        """Update payment with additional validation"""
        # Don't allow changing the from_user or to_user after creation
        validated_data.pop('from_user', None)
        validated_data.pop('to_user', None)
        
        return super().update(instance, validated_data)
