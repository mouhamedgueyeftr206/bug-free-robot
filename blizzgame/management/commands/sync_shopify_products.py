from django.core.management.base import BaseCommand
from blizzgame.shopify_utils import sync_products_from_shopify

class Command(BaseCommand):
    help = 'Synchronise les produits depuis Shopify'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force la synchronisation même si des produits existent déjà',
        )

    def handle(self, *args, **options):
        self.stdout.write('Début de la synchronisation des produits Shopify...')
        
        try:
            count = sync_products_from_shopify()
            self.stdout.write(
                self.style.SUCCESS(f'✅ Synchronisation terminée: {count} produits traités')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors de la synchronisation: {e}')
            )