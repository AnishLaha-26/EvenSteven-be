from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from .models import Group, GroupMember
from .balance_manager import BalanceManager
from expenses.models import Expense, ExpenseSplit, Payment
from settlements.models import Settlement

User = get_user_model()


class BalanceManagerTestCase(TestCase):
    def setUp(self):
        """Set up test data."""
        # Create test users
        self.user1 = User.objects.create_user(
            email='user1@test.com',
            password='testpass123'
        )
        self.user2 = User.objects.create_user(
            email='user2@test.com',
            password='testpass123'
        )
        self.user3 = User.objects.create_user(
            email='user3@test.com',
            password='testpass123'
        )
        
        # Create a test group
        self.group = Group.objects.create(
            name='Test Group',
            description='A test group',
            created_by=self.user1,
            currency='USD'
        )
        
        # Add members to the group
        self.member1 = self.group.add_member(self.user1, role='admin')
        self.member2 = self.group.add_member(self.user2)
        self.member3 = self.group.add_member(self.user3)
    
    def test_initial_balances_are_zero(self):
        """Test that new members start with zero balance."""
        self.assertEqual(self.member1.balance, Decimal('0.00'))
        self.assertEqual(self.member2.balance, Decimal('0.00'))
        self.assertEqual(self.member3.balance, Decimal('0.00'))
    
    def test_expense_without_splits_updates_payer_balance(self):
        """Test that creating an expense without splits updates the payer's balance."""
        # User1 pays $30 for dinner
        expense = Expense.objects.create(
            group=self.group,
            paid_by=self.user1,
            amount=Decimal('30.00'),
            description='Dinner',
            currency='USD'
        )
        
        # Check balances after expense creation
        updated_member1 = GroupMember.objects.get(user=self.user1, group=self.group)
        self.assertEqual(updated_member1.balance, Decimal('30.00'))  # User1 is owed $30
        
        # Other members should still have zero balance (no splits created yet)
        updated_member2 = GroupMember.objects.get(user=self.user2, group=self.group)
        updated_member3 = GroupMember.objects.get(user=self.user3, group=self.group)
        self.assertEqual(updated_member2.balance, Decimal('0.00'))
        self.assertEqual(updated_member3.balance, Decimal('0.00'))
    
    def test_expense_with_equal_splits(self):
        """Test expense with equal splits among all members."""
        # User1 pays $30 for dinner, split equally among 3 people
        expense = Expense.objects.create(
            group=self.group,
            paid_by=self.user1,
            amount=Decimal('30.00'),
            description='Dinner',
            currency='USD'
        )
        
        # Create equal splits ($10 each)
        ExpenseSplit.objects.create(
            expense=expense,
            user=self.user1,
            amount=Decimal('10.00')
        )
        ExpenseSplit.objects.create(
            expense=expense,
            user=self.user2,
            amount=Decimal('10.00')
        )
        ExpenseSplit.objects.create(
            expense=expense,
            user=self.user3,
            amount=Decimal('10.00')
        )
        
        # Check balances
        # User1: paid $30, owes $10 → balance = $30 - $10 = $20
        # User2: paid $0, owes $10 → balance = $0 - $10 = -$10
        # User3: paid $0, owes $10 → balance = $0 - $10 = -$10
        
        updated_member1 = GroupMember.objects.get(user=self.user1, group=self.group)
        updated_member2 = GroupMember.objects.get(user=self.user2, group=self.group)
        updated_member3 = GroupMember.objects.get(user=self.user3, group=self.group)
        
        self.assertEqual(updated_member1.balance, Decimal('20.00'))
        self.assertEqual(updated_member2.balance, Decimal('-10.00'))
        self.assertEqual(updated_member3.balance, Decimal('-10.00'))
    
    def test_payment_updates_balances(self):
        """Test that payments update balances correctly."""
        # First, create an expense scenario
        expense = Expense.objects.create(
            group=self.group,
            paid_by=self.user1,
            amount=Decimal('30.00'),
            description='Dinner',
            currency='USD'
        )
        
        ExpenseSplit.objects.create(expense=expense, user=self.user1, amount=Decimal('10.00'))
        ExpenseSplit.objects.create(expense=expense, user=self.user2, amount=Decimal('10.00'))
        ExpenseSplit.objects.create(expense=expense, user=self.user3, amount=Decimal('10.00'))
        
        # Now user2 pays user1 $10
        payment = Payment.objects.create(
            from_user=self.user2,
            to_user=self.user1,
            group=self.group,
            amount=Decimal('10.00'),
            currency='USD',
            description='Payment for dinner'
        )
        
        # Check balances after payment
        # User1: was owed $20, receives $10 → balance = $20 - $10 = $10
        # User2: owed $10, pays $10 → balance = -$10 + $10 = $0
        # User3: still owes $10 → balance = -$10
        
        updated_member1 = GroupMember.objects.get(user=self.user1, group=self.group)
        updated_member2 = GroupMember.objects.get(user=self.user2, group=self.group)
        updated_member3 = GroupMember.objects.get(user=self.user3, group=self.group)
        
        self.assertEqual(updated_member1.balance, Decimal('10.00'))
        self.assertEqual(updated_member2.balance, Decimal('0.00'))
        self.assertEqual(updated_member3.balance, Decimal('-10.00'))
    
    def test_balance_calculation_methods(self):
        """Test the balance calculation utility methods."""
        # Create a scenario with expenses and payments
        expense = Expense.objects.create(
            group=self.group,
            paid_by=self.user1,
            amount=Decimal('60.00'),
            description='Groceries',
            currency='USD'
        )
        
        ExpenseSplit.objects.create(expense=expense, user=self.user1, amount=Decimal('20.00'))
        ExpenseSplit.objects.create(expense=expense, user=self.user2, amount=Decimal('20.00'))
        ExpenseSplit.objects.create(expense=expense, user=self.user3, amount=Decimal('20.00'))
        
        # Test calculate_member_balance method
        calculated_balance1 = BalanceManager.calculate_member_balance(self.group, self.user1)
        calculated_balance2 = BalanceManager.calculate_member_balance(self.group, self.user2)
        calculated_balance3 = BalanceManager.calculate_member_balance(self.group, self.user3)
        
        self.assertEqual(calculated_balance1, Decimal('40.00'))  # paid $60, owes $20
        self.assertEqual(calculated_balance2, Decimal('-20.00'))  # paid $0, owes $20
        self.assertEqual(calculated_balance3, Decimal('-20.00'))  # paid $0, owes $20
        
        # Test get_group_balance_summary method
        summary = BalanceManager.get_group_balance_summary(self.group)
        
        self.assertEqual(summary['group_id'], self.group.id)
        self.assertEqual(summary['group_name'], self.group.name)
        self.assertEqual(summary['currency'], 'USD')
        self.assertEqual(len(summary['members']), 3)
        self.assertEqual(summary['total_owed'], Decimal('40.00'))
        self.assertEqual(summary['total_owing'], Decimal('40.00'))
        self.assertEqual(summary['net_balance'], Decimal('0.00'))
    
    def test_member_balance_details(self):
        """Test getting detailed balance information for a member."""
        # Create expense scenario
        expense = Expense.objects.create(
            group=self.group,
            paid_by=self.user1,
            amount=Decimal('45.00'),
            description='Restaurant',
            currency='USD'
        )
        
        ExpenseSplit.objects.create(expense=expense, user=self.user1, amount=Decimal('15.00'))
        ExpenseSplit.objects.create(expense=expense, user=self.user2, amount=Decimal('15.00'))
        ExpenseSplit.objects.create(expense=expense, user=self.user3, amount=Decimal('15.00'))
        
        # Get balance details for user1
        details = BalanceManager.get_member_balance_details(self.group, self.user1)
        
        self.assertEqual(details['user_id'], self.user1.id)
        self.assertEqual(details['current_balance'], Decimal('30.00'))
        self.assertEqual(details['breakdown']['expenses_paid'], Decimal('45.00'))
        self.assertEqual(details['breakdown']['expense_shares_owed'], Decimal('15.00'))
        self.assertEqual(details['status'], 'owed')
        
        # Get balance details for user2 (who owes money)
        details2 = BalanceManager.get_member_balance_details(self.group, self.user2)
        self.assertEqual(details2['current_balance'], Decimal('-15.00'))
        self.assertEqual(details2['status'], 'owes')
    
    def test_settlement_updates_balances(self):
        """Test that settlements update balances correctly."""
        # Create initial expense scenario
        expense = Expense.objects.create(
            group=self.group,
            paid_by=self.user1,
            amount=Decimal('30.00'),
            description='Lunch',
            currency='USD'
        )
        
        ExpenseSplit.objects.create(expense=expense, user=self.user1, amount=Decimal('10.00'))
        ExpenseSplit.objects.create(expense=expense, user=self.user2, amount=Decimal('10.00'))
        ExpenseSplit.objects.create(expense=expense, user=self.user3, amount=Decimal('10.00'))
        
        # Create a settlement: user2 settles their debt with user1
        settlement = Settlement.objects.create(
            from_user=self.user2,
            to_user=self.user1,
            group=self.group,
            amount=Decimal('10.00'),
            currency='USD',
            description='Settling lunch debt'
        )
        
        # Check balances after settlement
        # User1: was owed $20, receives settlement $10 → balance = $20 - $10 = $10
        # User2: owed $10, settles $10 → balance = -$10 + $10 = $0
        # User3: still owes $10 → balance = -$10
        
        updated_member1 = GroupMember.objects.get(user=self.user1, group=self.group)
        updated_member2 = GroupMember.objects.get(user=self.user2, group=self.group)
        updated_member3 = GroupMember.objects.get(user=self.user3, group=self.group)
        
        self.assertEqual(updated_member1.balance, Decimal('10.00'))
        self.assertEqual(updated_member2.balance, Decimal('0.00'))
        self.assertEqual(updated_member3.balance, Decimal('-10.00'))

