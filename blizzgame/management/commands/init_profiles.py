from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from blizzgame.models import Profile

class Command(BaseCommand):
    help = 'Initialise les profils existants avec des scores à 0'

    def handle(self, *args, **options):
        users_without_profile = User.objects.filter(profile__isnull=True)
        created_count = 0
        
        for user in users_without_profile:
            Profile.objects.create(
                user=user,
                id_user=user.id,
                score=0,
                appreciation_count=0
            )
            created_count += 1
            
        # Mettre à jour les profils existants avec des valeurs par défaut si nécessaire
        profiles_to_update = Profile.objects.filter(score__isnull=True)
        for profile in profiles_to_update:
            profile.score = 0
            profile.appreciation_count = 0
            profile.save()
            
        self.stdout.write(
            self.style.SUCCESS(
                f'Profils créés: {created_count}, '
                f'Profils mis à jour: {profiles_to_update.count()}'
            )
        )
