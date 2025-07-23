from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db.models import Q, Sum, Count
from django.db import models
from django_filters.rest_framework import DjangoFilterBackend
from .models import Expense, ExpenseSplit, Payment
from .serializers import ExpenseSerializer, ExpenseSplitSerializer, PaymentSerializer
from groups.models import Group, GroupMember
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ExpenseListCreateView(generics.ListCreateAPIView):
    """
    List all expenses for groups the user belongs to, or create a new expense.
    """
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        # Get all groups the user is a member of
        user_groups = GroupMember.objects.filter(user=user).values_list('group', flat=True)
        # Return expenses from those groups
        return Expense.objects.filter(group__in=user_groups).select_related(
            'paid_by', 'group'
        ).prefetch_related('splits__user')
    
    def perform_create(self, serializer):
        serializer.save()


class ExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete an expense.
    """
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        # Get all groups the user is a member of
        user_groups = GroupMember.objects.filter(user=user).values_list('group', flat=True)
        # Return expenses from those groups
        return Expense.objects.filter(group__in=user_groups).select_related(
            'paid_by', 'group'
        ).prefetch_related('splits__user')


class GroupExpenseListView(generics.ListAPIView):
    """
    List all expenses for a specific group.
    """
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        group_id = self.kwargs['group_id']
        user = self.request.user
        
        # Verify user is a member of the group
        group = get_object_or_404(Group, id=group_id)
        if not GroupMember.objects.filter(group=group, user=user).exists():
            return Expense.objects.none()
        
        return Expense.objects.filter(group=group).select_related(
            'paid_by', 'group'
        ).prefetch_related('splits__user')


class PaymentListCreateView(generics.ListCreateAPIView):
    """
    List all payments for groups the user belongs to, or create a new payment.
    Supports filtering by group, date range, and amount range.
    Includes pagination and search functionality.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['group', 'currency', 'payment_date']
    search_fields = ['description', 'from_user__email', 'to_user__email']
    ordering_fields = ['payment_date', 'amount', 'created_at']
    ordering = ['-payment_date', '-created_at']
    
    def get_queryset(self):
        user = self.request.user
        queryset = Payment.objects.filter(
            Q(from_user=user) | Q(to_user=user)
        ).select_related('from_user', 'to_user', 'group')
        
        # Additional filtering
        group_id = self.request.query_params.get('group_id')
        if group_id:
            queryset = queryset.filter(group_id=group_id)
            
        # Date range filtering
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(payment_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(payment_date__lte=date_to)
            
        # Amount range filtering
        amount_min = self.request.query_params.get('amount_min')
        amount_max = self.request.query_params.get('amount_max')
        if amount_min:
            queryset = queryset.filter(amount__gte=amount_min)
        if amount_max:
            queryset = queryset.filter(amount__lte=amount_max)
            
        return queryset
    
    def perform_create(self, serializer):
        try:
            payment = serializer.save()
            logger.info(f"Payment created: {payment.id} from {payment.from_user.email} to {payment.to_user.email}")
        except Exception as e:
            logger.error(f"Error creating payment: {str(e)}")
            raise
    
    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error listing payments for user {request.user.email}: {str(e)}")
            return Response(
                {'error': 'Unable to retrieve payments. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update or delete a payment.
    Only the payment creator can update or delete the payment.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        # Get payments where user is either sender or receiver
        return Payment.objects.filter(
            Q(from_user=user) | Q(to_user=user)
        ).select_related('from_user', 'to_user', 'group')
    
    def update(self, request, *args, **kwargs):
        payment = self.get_object()
        # Only the payment creator can update
        if payment.from_user != request.user:
            return Response(
                {'error': 'You can only update payments you created.'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error updating payment {payment.id}: {str(e)}")
            return Response(
                {'error': 'Unable to update payment. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def destroy(self, request, *args, **kwargs):
        payment = self.get_object()
        # Only the payment creator can delete
        if payment.from_user != request.user:
            return Response(
                {'error': 'You can only delete payments you created.'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            logger.info(f"Payment deleted: {payment.id} by {request.user.email}")
            return super().destroy(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error deleting payment {payment.id}: {str(e)}")
            return Response(
                {'error': 'Unable to delete payment. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class GroupPaymentListView(generics.ListAPIView):
    """
    List all payments for a specific group.
    Includes filtering, search, and pagination.
    """
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['description', 'from_user__email', 'to_user__email']
    ordering_fields = ['payment_date', 'amount', 'created_at']
    ordering = ['-payment_date', '-created_at']
    
    def get_queryset(self):
        group_id = self.kwargs['group_id']
        user = self.request.user
        
        # Verify user is a member of the group
        group = get_object_or_404(Group, id=group_id)
        if not GroupMember.objects.filter(group=group, user=user).exists():
            return Payment.objects.none()
        
        queryset = Payment.objects.filter(group=group).select_related(
            'from_user', 'to_user', 'group'
        )
        
        # Additional filtering
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(payment_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(payment_date__lte=date_to)
            
        return queryset
    
    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error listing group payments for group {kwargs.get('group_id')}: {str(e)}")
            return Response(
                {'error': 'Unable to retrieve group payments. Please try again later.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def user_expense_summary(request):
    """
    Get a summary of user's expenses across all groups.
    """
    user = request.user
    user_groups = GroupMember.objects.filter(user=user).values_list('group', flat=True)
    
    # Expenses paid by user
    expenses_paid = Expense.objects.filter(
        paid_by=user, group__in=user_groups
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    # Amount user owes (from expense splits)
    amount_owed = ExpenseSplit.objects.filter(
        user=user, expense__group__in=user_groups
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    # Payments made by user
    payments_made = Payment.objects.filter(
        from_user=user, group__in=user_groups
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    # Payments received by user
    payments_received = Payment.objects.filter(
        to_user=user, group__in=user_groups
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    return Response({
        'expenses_paid': expenses_paid,
        'amount_owed': amount_owed,
        'payments_made': payments_made,
        'payments_received': payments_received,
        'net_balance': expenses_paid - amount_owed + payments_received - payments_made
    })


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def payment_statistics(request):
    """
    Get payment statistics for the authenticated user.
    """
    user = request.user
    
    try:
        # Get user's groups
        user_groups = GroupMember.objects.filter(user=user).values_list('group', flat=True)
        
        # Payment statistics
        payments_made = Payment.objects.filter(from_user=user, group__in=user_groups)
        payments_received = Payment.objects.filter(to_user=user, group__in=user_groups)
        
        # Aggregate statistics
        total_paid = payments_made.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_received = payments_received.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        payment_count_made = payments_made.count()
        payment_count_received = payments_received.count()
        
        # Recent payments (last 30 days)
        from datetime import datetime, timedelta
        thirty_days_ago = datetime.now().date() - timedelta(days=30)
        recent_payments_made = payments_made.filter(payment_date__gte=thirty_days_ago).count()
        recent_payments_received = payments_received.filter(payment_date__gte=thirty_days_ago).count()
        
        # Payment by currency
        currency_breakdown = Payment.objects.filter(
            Q(from_user=user) | Q(to_user=user),
            group__in=user_groups
        ).values('currency').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('-total_amount')
        
        return Response({
            'total_paid': total_paid,
            'total_received': total_received,
            'payment_count_made': payment_count_made,
            'payment_count_received': payment_count_received,
            'recent_payments_made': recent_payments_made,
            'recent_payments_received': recent_payments_received,
            'net_balance': total_received - total_paid,
            'currency_breakdown': list(currency_breakdown)
        })
    except Exception as e:
        logger.error(f"Error getting payment statistics for user {user.email}: {str(e)}")
        return Response(
            {'error': 'Unable to retrieve payment statistics.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def group_payment_summary(request, group_id):
    """
    Get payment summary for a specific group.
    Shows who owes what to whom based on expenses and payments.
    """
    user = request.user
    
    try:
        # Verify user is a member of the group
        group = get_object_or_404(Group, id=group_id)
        if not GroupMember.objects.filter(group=group, user=user).exists():
            return Response(
                {'error': 'You are not a member of this group.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get all group members
        group_members = GroupMember.objects.filter(group=group).select_related('user')
        member_balances = {}
        
        # Initialize balances for all members
        for member in group_members:
            member_balances[member.user.id] = {
                'user_id': member.user.id,
                'user_email': member.user.email,
                'user_name': member.user.get_full_name() or member.user.email,
                'total_paid': Decimal('0'),
                'total_owed': Decimal('0'),
                'payments_made': Decimal('0'),
                'payments_received': Decimal('0'),
                'net_balance': Decimal('0')
            }
        
        # Calculate expenses paid by each member
        expenses = Expense.objects.filter(group=group).select_related('paid_by')
        for expense in expenses:
            if expense.paid_by.id in member_balances:
                member_balances[expense.paid_by.id]['total_paid'] += expense.amount
        
        # Calculate amounts owed by each member (from splits)
        splits = ExpenseSplit.objects.filter(
            expense__group=group
        ).select_related('user', 'expense')
        for split in splits:
            if split.user.id in member_balances:
                member_balances[split.user.id]['total_owed'] += split.amount
        
        # Calculate payments made and received
        payments = Payment.objects.filter(group=group).select_related('from_user', 'to_user')
        for payment in payments:
            if payment.from_user.id in member_balances:
                member_balances[payment.from_user.id]['payments_made'] += payment.amount
            if payment.to_user.id in member_balances:
                member_balances[payment.to_user.id]['payments_received'] += payment.amount
        
        # Calculate net balances
        for member_id, balance in member_balances.items():
            balance['net_balance'] = (
                balance['total_paid'] - balance['total_owed'] + 
                balance['payments_received'] - balance['payments_made']
            )
        
        # Group statistics
        total_expenses = expenses.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_payments = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        
        return Response({
            'group_id': group_id,
            'group_name': group.name,
            'member_balances': list(member_balances.values()),
            'total_expenses': total_expenses,
            'total_payments': total_payments,
            'settlement_suggestions': _generate_settlement_suggestions(member_balances)
        })
    except Exception as e:
        logger.error(f"Error getting group payment summary for group {group_id}: {str(e)}")
        return Response(
            {'error': 'Unable to retrieve group payment summary.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def _generate_settlement_suggestions(member_balances):
    """
    Generate settlement suggestions to minimize the number of transactions.
    """
    # Separate creditors (positive balance) and debtors (negative balance)
    creditors = []
    debtors = []
    
    for balance in member_balances.values():
        net = balance['net_balance']
        if net > 0:
            creditors.append({
                'user_id': balance['user_id'],
                'user_name': balance['user_name'],
                'amount': net
            })
        elif net < 0:
            debtors.append({
                'user_id': balance['user_id'],
                'user_name': balance['user_name'],
                'amount': abs(net)
            })
    
    # Generate settlement suggestions
    suggestions = []
    creditors_copy = creditors.copy()
    debtors_copy = debtors.copy()
    
    for debtor in debtors_copy:
        debt_remaining = debtor['amount']
        
        for creditor in creditors_copy:
            if debt_remaining <= 0 or creditor['amount'] <= 0:
                continue
                
            settlement_amount = min(debt_remaining, creditor['amount'])
            
            suggestions.append({
                'from_user_id': debtor['user_id'],
                'from_user_name': debtor['user_name'],
                'to_user_id': creditor['user_id'],
                'to_user_name': creditor['user_name'],
                'amount': settlement_amount
            })
            
            debt_remaining -= settlement_amount
            creditor['amount'] -= settlement_amount
    
    return suggestions
