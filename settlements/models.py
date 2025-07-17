from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal


class Settlement(models.Model):
    CURRENCY_CHOICES = [
        ('USD', 'US Dollar'),
        ('INR', 'Indian Rupee'),
        ('EUR', 'Euro'),
        ('GBP', 'British Pound'),
    ]
    
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='settlements_initiated'
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='settlements_received'
    )
    group = models.ForeignKey(
        'groups.Group',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='settlements'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='INR')
    description = models.TextField(blank=True, null=True)
    settled_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-settled_at', '-created_at']
        unique_together = ('from_user', 'to_user', 'group', 'settled_at', 'amount')
    
    def __str__(self):
        group_info = f" in {self.group.name}" if self.group else ""
        return f"{self.from_user.email} settled {self.amount} {self.currency} to {self.to_user.email}{group_info}"
    
    def save(self, *args, **kwargs):
        # Ensure the amount is positive
        if self.amount <= 0:
            raise ValueError("Settlement amount must be positive.")
        super().save(*args, **kwargs)
