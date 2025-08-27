from django.core.management.base import BaseCommand
from django.utils import timezone
from blizzgame.models import Highlight
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Supprime les Highlights expirés (après 48h) et leurs données associées'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les Highlights qui seraient supprimés sans les supprimer',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        
        # Trouver les highlights expirés
        expired_highlights = Highlight.objects.filter(
            expires_at__lt=now,
            is_active=True
        )
        
        count = expired_highlights.count()
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING(f'Mode dry-run: {count} Highlights seraient supprimés')
            )
            
            for highlight in expired_highlights[:10]:  # Afficher les 10 premiers
                self.stdout.write(f'- {highlight.author.username}: {highlight.caption[:50]}...')
            
            if count > 10:
                self.stdout.write(f'... et {count - 10} autres')
        
        else:
            if count > 0:
                # Supprimer les highlights expirés
                # Les likes, commentaires, vues et partages seront supprimés automatiquement
                # grâce aux relations CASCADE dans les modèles
                deleted_count, deleted_details = expired_highlights.delete()
                
                self.stdout.write(
                    self.style.SUCCESS(f'✅ {count} Highlights expirés supprimés')
                )
                
                # Afficher les détails de suppression
                for model, model_count in deleted_details.items():
                    if model_count > 0:
                        self.stdout.write(f'  - {model}: {model_count} supprimés')
                
                logger.info(f"Nettoyage automatique: {count} Highlights expirés supprimés")
            
            else:
                self.stdout.write(
                    self.style.SUCCESS('Aucun Highlight expiré à supprimer')
                )