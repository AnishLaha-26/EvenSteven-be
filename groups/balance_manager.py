from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Q
from .models import GroupMember, Group
from expenses.models import Expense, ExpenseSplit, Payment
from settlements.models import Settlement


class BalanceManager:
    """
    Manages balance calculations and updates for group members.
    
    Balance Logic:
    - When a member pays for an expense, their balance increases by the amount they paid
    - When a member owes money for an expense split, their balance decreases by their share
    - When a member makes a payment to another member, their balance increases
    - When a member receives a payment from another member, their balance decreases
    - Settlements adjust balances between members
    
    Positive balance = member is owed money
    Negative balance = member owes money
    """
    
    @staticmethod
    def initialize_member_balance(group, user):
        """Initialize balance to 0 when a member joins a group."""
        try:
            member = GroupMember.objects.get(group=group, user=user)
            member.balance = Decimal('0.00')
            member.save(update_fields=['balance'])
            return member
        except GroupMember.DoesNotExist:
            return None
    
    @staticmethod
    def calculate_member_balance(group, user):
        """
        Calculate the current balance for a member in a group based on all transactions.
        
        Returns:
            Decimal: The calculated balance (positive = owed money, negative = owes money)
        """
        balance = Decimal('0.00')
        
        # 1. Add amounts paid by this user for group expenses
        expenses_paid = Expense.objects.filter(
            group=group,
            paid_by=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        balance += expenses_paid
        
        # 2. Subtract amounts owed by this user from expense splits
        expense_splits = ExpenseSplit.objects.filter(
            expense__group=group,
            user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        balance -= expense_splits
        
        # 3. Add payments made by this user to other members in the group
        payments_made = Payment.objects.filter(
            group=group,
            from_user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        balance += payments_made
        
        # 4. Subtract payments received by this user from other members in the group
        payments_received = Payment.objects.filter(
            group=group,
            to_user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        balance -= payments_received
        
        # 5. Add settlements initiated by this user
        settlements_made = Settlement.objects.filter(
            group=group,
            from_user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        balance += settlements_made
        
        # 6. Subtract settlements received by this user
        settlements_received = Settlement.objects.filter(
            group=group,
            to_user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        balance -= settlements_received
        
        return balance
    
    @staticmethod
    def update_member_balance(group, user):
        """
        Update the stored balance for a member based on calculated balance.
        
        Returns:
            GroupMember: The updated member object
        """
        try:
            member = GroupMember.objects.get(group=group, user=user)
            calculated_balance = BalanceManager.calculate_member_balance(group, user)
            member.balance = calculated_balance
            member.save(update_fields=['balance'])
            return member
        except GroupMember.DoesNotExist:
            return None
    
    @staticmethod
    def update_all_group_balances(group):
        """
        Update balances for all active members in a group.
        
        Returns:
            list: List of updated GroupMember objects
        """
        updated_members = []
        active_members = GroupMember.objects.filter(
            group=group,
            status='active'
        )
        
        for member in active_members:
            updated_member = BalanceManager.update_member_balance(group, member.user)
            if updated_member:
                updated_members.append(updated_member)
        
        return updated_members
    
    @staticmethod
    def get_group_balance_summary(group):
        """
        Get a summary of all balances in a group.
        
        Returns:
            dict: Summary containing member balances and totals
        """
        members = GroupMember.objects.filter(
            group=group,
            status='active'
        ).select_related('user')
        
        summary = {
            'group_id': group.id,
            'group_name': group.name,
            'currency': group.currency,
            'members': [],
            'total_owed': Decimal('0.00'),
            'total_owing': Decimal('0.00'),
            'net_balance': Decimal('0.00')
        }
        
        for member in members:
            # Ensure balance is up to date
            current_balance = BalanceManager.calculate_member_balance(group, member.user)
            
            member_data = {
                'user_id': member.user.id,
                'user_email': member.user.email,
                'user_name': getattr(member.user, 'first_name', '') + ' ' + getattr(member.user, 'last_name', ''),
                'balance': current_balance,
                'status': 'owed' if current_balance > 0 else 'owes' if current_balance < 0 else 'settled'
            }
            
            summary['members'].append(member_data)
            
            if current_balance > 0:
                summary['total_owed'] += current_balance
            elif current_balance < 0:
                summary['total_owing'] += abs(current_balance)
        
        summary['net_balance'] = summary['total_owed'] - summary['total_owing']
        
        return summary
    
    @staticmethod
    def get_member_balance_details(group, user):
        """
        Get detailed balance information for a specific member.
        
        Returns:
            dict: Detailed balance breakdown
        """
        try:
            member = GroupMember.objects.get(group=group, user=user)
        except GroupMember.DoesNotExist:
            return None
        
        # Calculate components
        expenses_paid = Expense.objects.filter(
            group=group,
            paid_by=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        expense_splits = ExpenseSplit.objects.filter(
            expense__group=group,
            user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        payments_made = Payment.objects.filter(
            group=group,
            from_user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        payments_received = Payment.objects.filter(
            group=group,
            to_user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        settlements_made = Settlement.objects.filter(
            group=group,
            from_user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        settlements_received = Settlement.objects.filter(
            group=group,
            to_user=user
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        current_balance = BalanceManager.calculate_member_balance(group, user)
        
        return {
            'user_id': user.id,
            'user_email': user.email,
            'group_id': group.id,
            'group_name': group.name,
            'currency': group.currency,
            'current_balance': current_balance,
            'breakdown': {
                'expenses_paid': expenses_paid,
                'expense_shares_owed': expense_splits,
                'payments_made': payments_made,
                'payments_received': payments_received,
                'settlements_made': settlements_made,
                'settlements_received': settlements_received
            },
            'status': 'owed' if current_balance > 0 else 'owes' if current_balance < 0 else 'settled'
        }
    
    @staticmethod
    @transaction.atomic
    def process_expense_balance_update(expense):
        """
        Update balances for all affected members when an expense is created or updated.
        
        Args:
            expense: Expense object
        """
        group = expense.group
        
        # Update balance for the person who paid
        BalanceManager.update_member_balance(group, expense.paid_by)
        
        # Update balances for all users with expense splits
        split_users = ExpenseSplit.objects.filter(expense=expense).values_list('user', flat=True)
        for user_id in split_users:
            try:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.get(id=user_id)
                BalanceManager.update_member_balance(group, user)
            except User.DoesNotExist:
                continue
    
    @staticmethod
    @transaction.atomic
    def process_payment_balance_update(payment):
        """
        Update balances for both users involved in a payment.
        
        Args:
            payment: Payment object
        """
        if payment.group:
            BalanceManager.update_member_balance(payment.group, payment.from_user)
            BalanceManager.update_member_balance(payment.group, payment.to_user)
    
    @staticmethod
    @transaction.atomic
    def process_settlement_balance_update(settlement):
        """
        Update balances for both users involved in a settlement.
        
        Args:
            settlement: Settlement object
        """
        if settlement.group:
            BalanceManager.update_member_balance(settlement.group, settlement.from_user)
            BalanceManager.update_member_balance(settlement.group, settlement.to_user)
