from django.core.management.base import BaseCommand
from blizzgame.models import ShopifyIntegration


class Command(BaseCommand):
    help = "Affiche l'intégration Shopify active (diagnostic)"

    def handle(self, *args, **options):
        integ = ShopifyIntegration.objects.filter(is_active=True).order_by('-updated_at').first()
        if not integ:
            self.stdout.write(self.style.ERROR('Aucune intégration Shopify active.'))
            return
        token_len = len(integ.access_token or '')
        secret_len = len(integ.webhook_secret or '')
        self.stdout.write('Shop name: %s' % integ.shop_name)
        self.stdout.write('Shop URL: %s' % integ.shop_url)
        self.stdout.write('Access token length: %s' % token_len)
        self.stdout.write('Webhook secret length: %s' % secret_len)

