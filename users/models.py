from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class CustomUserManager(BaseUserManager):
    """Custom user model manager where email is the unique identifier"""
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        return self.create_user(email, password, **extra_fields)

class User(AbstractUser):
    username = None
    email = models.EmailField(_('email address'), unique=True)
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    is_active = models.BooleanField(_('active'), default=True)
    last_login = models.DateTimeField(_('last login'), auto_now=True)
    
    # Additional fields for user preferences
    preferred_currency = models.CharField(
        max_length=3,
        default='INR',
        choices=[
            ('USD', 'US Dollar'),
            ('INR', 'Indian Rupee'),
            ('EUR', 'Euro'),
            ('GBP', 'British Pound'),
        ]
    )
    language = models.CharField(
        max_length=10,
        default='en',
        choices=[
            ('en', 'English'),
            ('hi', 'हिंदी'),
            ('es', 'Español'),
            ('fr', 'Français'),
        ]
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        ordering = ['-date_joined']
        verbose_name = _('user')
        verbose_name_plural = _('users')

    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name} {self.last_name}"
        return full_name.strip()
    
    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.email.split('@')[0]


class Profile(models.Model):
    """User profile with additional information"""
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text=_('Phone number in international format (e.g., +91XXXXXXXXXX)')
    )
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        blank=True,
        null=True,
        help_text=_('Profile picture')
    )
    bio = models.TextField(
        blank=True,
        null=True,
        help_text=_('A short bio about yourself')
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text=_('Date of birth')
    )
    timezone = models.CharField(
        max_length=50,
        default='Asia/Kolkata',
        help_text=_('User\'s timezone')
    )
    email_notifications = models.BooleanField(
        default=True,
        help_text=_('Enable email notifications')
    )
    push_notifications = models.BooleanField(
        default=True,
        help_text=_('Enable push notifications')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email}'s Profile"
    
    class Meta:
        ordering = ['-created_at']


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a profile for the user when a new user is created."""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the user's profile when the user is saved."""
    instance.profile.save()
