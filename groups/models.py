from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
from django.db.models.signals import pre_save
from django.dispatch import receiver
import random
import string

def generate_join_code():
    """Generate a unique 6-digit alphanumeric code."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

class Group(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='created_groups',
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=10,
        choices=[('active', 'Active'), ('archived', 'Archived'), ('deleted', 'Deleted')],
        default='active'
    )
    currency = models.CharField(max_length=3, default='USD')
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='admin_of_groups'
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='GroupMember',
        related_name='member_of_groups'
    )
    join_code = models.CharField(max_length=6, unique=True, blank=True)
    
    def __str__(self):
        return self.name

    def add_member(self, user, role='member'):
        """Add a user to the group."""
        return GroupMember.objects.create(
            user=user,
            group=self,
            role=role,
            status='active'
        )

    def remove_member(self, user):
        """Remove a user from the group."""
        return GroupMember.objects.filter(user=user, group=self).delete()

    class Meta:
        ordering = ['-created_at']

@receiver(pre_save, sender=Group)
def generate_join_code_on_save(sender, instance, **kwargs):
    if not instance.join_code:  # Only generate if it doesn't exist
        instance.join_code = generate_join_code()
        while Group.objects.filter(join_code=instance.join_code).exists():
            instance.join_code = generate_join_code()

class GroupMember(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('member', 'Member'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('removed', 'Removed'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='group_memberships'
    )
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'group')
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.group.name} ({self.role})"

class GroupSettings(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='settings')
    notifications_enabled = models.BooleanField(default=True)
    privacy = models.CharField(
        max_length=10,
        choices=[('public', 'Public'), ('private', 'Private')],
        default='private'
    )
    payment_methods = models.JSONField(default=list)
    
    def __str__(self):
        return f"Settings for {self.group.name}"

class Transaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('settled', 'Settled'),
        ('cancelled', 'Cancelled'),
    ]
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='transactions')
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='paid_transactions'
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='participated_transactions'
    )
    category = models.CharField(max_length=50)
    date = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.description} - {self.amount} {self.group.currency}"

class GroupInvitation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='invitations')
    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    invitee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='received_invitations'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        unique_together = ('group', 'invitee')
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.inviter.email} invited {self.invitee.email} to {self.group.name}"


class GroupPayment(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    currency = models.CharField(max_length=3, default='USD')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.amount} {self.currency} for {self.group.name}"