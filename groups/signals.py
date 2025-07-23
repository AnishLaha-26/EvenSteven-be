from django.db.models.signals import post_save, post_delete, m2m_changed
from django.dispatch import receiver
from .models import GroupMember, Group
from .balance_manager import BalanceManager
from expenses.models import Expense, ExpenseSplit, Payment
from settlements.models import Settlement
import threading

# Thread-local storage to prevent signal recursion
_thread_locals = threading.local()


@receiver(post_save, sender=GroupMember)
def initialize_member_balance(sender, instance, created, **kwargs):
    """Initialize balance to 0 when a new member joins a group."""
    if created and instance.status == 'active':
        BalanceManager.initialize_member_balance(instance.group, instance.user)


@receiver(post_save, sender=Expense)
def update_balances_on_expense_change(sender, instance, created, **kwargs):
    """Update balances when an expense is created or modified."""
    BalanceManager.process_expense_balance_update(instance)


@receiver(post_delete, sender=Expense)
def update_balances_on_expense_delete(sender, instance, **kwargs):
    """Update balances when an expense is deleted."""
    # When an expense is deleted, we need to recalculate balances for affected users
    group = instance.group
    
    # Update balance for the person who paid
    BalanceManager.update_member_balance(group, instance.paid_by)
    
    # Update balances for all users who had splits for this expense
    # Note: ExpenseSplit objects are cascade deleted, so we need to get them before deletion
    # This signal runs after deletion, so we'll update all group members to be safe
    BalanceManager.update_all_group_balances(group)


@receiver(post_save, sender=ExpenseSplit)
def update_balances_on_split_change(sender, instance, created, **kwargs):
    """Update balances when an expense split is created or modified."""
    BalanceManager.update_member_balance(instance.expense.group, instance.user)
    # Also update the payer's balance in case the split affects the total
    BalanceManager.update_member_balance(instance.expense.group, instance.expense.paid_by)


@receiver(post_delete, sender=ExpenseSplit)
def update_balances_on_split_delete(sender, instance, **kwargs):
    """Update balances when an expense split is deleted."""
    BalanceManager.update_member_balance(instance.expense.group, instance.user)
    BalanceManager.update_member_balance(instance.expense.group, instance.expense.paid_by)


@receiver(post_save, sender=Payment)
def update_balances_on_payment_change(sender, instance, created, **kwargs):
    """Update balances when a payment is created or modified."""
    BalanceManager.process_payment_balance_update(instance)


@receiver(post_delete, sender=Payment)
def update_balances_on_payment_delete(sender, instance, **kwargs):
    """Update balances when a payment is deleted."""
    if instance.group:
        BalanceManager.update_member_balance(instance.group, instance.from_user)
        BalanceManager.update_member_balance(instance.group, instance.to_user)


@receiver(post_save, sender=Settlement)
def update_balances_on_settlement_change(sender, instance, created, **kwargs):
    """Update balances when a settlement is created or modified."""
    BalanceManager.process_settlement_balance_update(instance)


@receiver(post_delete, sender=Settlement)
def update_balances_on_settlement_delete(sender, instance, **kwargs):
    """Update balances when a settlement is deleted."""
    if instance.group:
        BalanceManager.update_member_balance(instance.group, instance.from_user)
        BalanceManager.update_member_balance(instance.group, instance.to_user)


@receiver(post_save, sender=GroupMember)
def handle_member_status_change(sender, instance, created, **kwargs):
    """Handle balance updates when member status changes."""
    # Skip balance updates during member creation to avoid recursion
    # Balance initialization is handled separately
    if not created and hasattr(instance, '_skip_balance_update'):
        return
        
    if not created:  # Only for updates, not creation
        # If member is being removed or deactivated, we might want to settle their balance
        if instance.status in ['removed', 'inactive']:
            # For now, just recalculate all group balances to ensure consistency
            BalanceManager.update_all_group_balances(instance.group)
        elif instance.status == 'active':
            # If member is being reactivated, update their balance
            BalanceManager.update_member_balance(instance.group, instance.user)
