from django.apps import AppConfig
from django.db.models.signals import post_save


def create_user_profile(sender, instance, created, **kwargs):
    """Create a profile for each new user if it doesn't exist"""
    if created:
        from .models import Profile
        Profile.objects.get_or_create(user=instance)


def save_user_profile(sender, instance, **kwargs):
    """Save the profile when the user is saved"""
    instance.profile.save()


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    verbose_name = 'User Management'

    def ready(self):
        # Import here to avoid AppRegistryNotReady error
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Connect the signals
        post_save.connect(create_user_profile, sender=User)
        post_save.connect(save_user_profile, sender=User)
