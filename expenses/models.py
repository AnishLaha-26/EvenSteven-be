from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class Expense(models.Model):
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('INR', 'Indian Rupee'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ]
    
    group = models.ForeignKey('groups.Group', on_delete=models.CASCADE, related_name='expenses')
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expenses_paid')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='INR')
    description = models.CharField(max_length=200)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.description} - {self.amount} {self.currency} in {self.group.name}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Update any related splits if needed
        if not hasattr(self, '_dirty') or self._dirty:
            self._update_splits()
    
    def _update_splits(self):
        # This method can be used to update splits when the expense is updated
        pass


class ExpenseSplit(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name='splits')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='expense_splits')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('expense', 'user')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} owes {self.amount} for {self.expense}"
    
    def save(self, *args, **kwargs):
        # Calculate amount based on percentage if percentage is provided
        if self.percentage is not None and not self.amount:
            self.amount = (self.expense.amount * self.percentage) / 100
        super().save(*args, **kwargs)


class Payment(models.Model):
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments_made'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='payments_received'
    )
    group = models.ForeignKey('groups.Group', on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=Expense.CURRENCY_CHOICES, default='INR')
    description = models.TextField(blank=True, null=True)
    payment_date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"{self.from_user.email} paid {self.to_user.email} {self.amount} {self.currency}"
