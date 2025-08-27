from django.core.management.base import BaseCommand
from blizzgame.models import ShopifyIntegration, ProductCategory
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Configure l\'intégration Shopify pour le dropshipping'

    def add_arguments(self, parser):
        parser.add_argument('--shop-name', type=str, help='Nom de la boutique Shopify')
        parser.add_argument('--access-token', type=str, help='Token d\'accès Shopify')
        parser.add_argument('--shop-url', type=str, help='URL de la boutique Shopify')
        parser.add_argument('--webhook-secret', type=str, help='Secret HMAC pour vérifier les webhooks (API secret key)')

    def handle(self, *args, **options):
        shop_name = options.get('shop_name')
        access_token = options.get('access_token')
        shop_url = options.get('shop_url')
        webhook_secret = options.get('webhook_secret')

        if not all([shop_name, access_token, shop_url]):
            self.stdout.write(
                self.style.ERROR(
                    'Tous les paramètres sont requis: --shop-name, --access-token, --shop-url'
                )
            )
            return

        # Créer ou mettre à jour l'intégration Shopify
        integration, created = ShopifyIntegration.objects.update_or_create(
            shop_name=shop_name,
            defaults={
                'shop_url': shop_url,
                'access_token': access_token,
                'is_active': True,
                'webhook_secret': webhook_secret or ''
            }
        )

        # Désactiver les autres intégrations actives
        from blizzgame.models import ShopifyIntegration as _SI
        _SI.objects.exclude(pk=integration.pk).update(is_active=False)

        if created:
            self.stdout.write(
                self.style.SUCCESS(f'Intégration Shopify créée pour: {shop_name}')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Intégration Shopify mise à jour pour: {shop_name}')
            )

        # Créer des catégories par défaut si elles n'existent pas
        default_categories = [
            {
                'name': 'Manettes Gaming',
                'description': 'Manettes de jeu professionnelles pour tous les supports',
            },
            {
                'name': 'Accessoires Gaming',
                'description': 'Accessoires pour améliorer votre expérience de jeu',
            },
            {
                'name': 'Casques Gaming',
                'description': 'Casques audio gaming haute qualité',
            },
            {
                'name': 'Claviers Gaming',
                'description': 'Claviers mécaniques pour gamers',
            },
            {
                'name': 'Souris Gaming',
                'description': 'Souris gaming haute précision',
            },
            {
                'name': 'Écrans Gaming',
                'description': 'Moniteurs gaming haute performance',
            },
        ]

        for cat_data in default_categories:
            category, created = ProductCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'slug': slugify(cat_data['name']),
                    'description': cat_data['description'],
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f'Catégorie créée: {category.name}')

        self.stdout.write(
            self.style.SUCCESS(
                '\n✅ Configuration terminée!\n'
                'Prochaines étapes:\n'
                '1. Synchronisez les produits: python manage.py sync_shopify_products\n'
                '2. Configurez les webhooks Shopify pour pointer vers /shop/payment/cinetpay/notification/\n'
                '3. Testez le processus de commande\n'
            )
        )