from django.core.management.base import BaseCommand
from django.utils.text import slugify
from blizzgame.models import ProductCategory, Product, ProductImage, ProductVariant
import os
from django.conf import settings

class Command(BaseCommand):
    help = 'Populate the shop with sample data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating sample e-commerce data...'))

        # Create categories
        categories_data = [
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
        ]

        categories = {}
        for cat_data in categories_data:
            category, created = ProductCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={
                    'slug': slugify(cat_data['name']),
                    'description': cat_data['description'],
                    'is_active': True,
                }
            )
            categories[cat_data['name']] = category
            if created:
                self.stdout.write(f'Created category: {category.name}')

        # Create products
        products_data = [
            {
                'name': 'Manette Pro Gaming Wiio',
                'category': 'Manettes Gaming',
                'price': 45000,
                'short_description': 'Manette gaming professionnelle avec vibrations et LED',
                'description': '''Manette gaming professionnelle Wiio avec:
- Vibrations haute précision
- LED RGB personnalisables
- Ergonomie optimisée pour de longues sessions
- Compatible PC, PS4, PS5, Xbox
- Garantie 2 ans''',
                'is_featured': True,
            },
            {
                'name': 'Gants Gaming Pro',
                'category': 'Accessoires Gaming',
                'price': 15000,
                'short_description': 'Gants gaming anti-transpiration pour une meilleure prise',
                'description': '''Gants gaming professionnels:
- Matière respirante anti-transpiration
- Grip renforcé sur les doigts
- Taille ajustable
- Lavable en machine
- Améliore la précision et le confort''',
                'is_featured': True,
            },
            {
                'name': 'Power Bank Gaming 20000mAh',
                'category': 'Accessoires Gaming',
                'price': 25000,
                'short_description': 'Batterie externe haute capacité pour gaming mobile',
                'description': '''Power Bank gaming 20000mAh:
- Charge rapide 18W
- 2 ports USB + 1 port USB-C
- Affichage LED de la batterie
- Compatible tous smartphones
- Design gaming avec LED''',
                'is_featured': False,
            },
            {
                'name': 'Casque Gaming RGB',
                'category': 'Casques Gaming',
                'price': 35000,
                'short_description': 'Casque gaming 7.1 avec micro et éclairage RGB',
                'description': '''Casque gaming professionnel:
- Son surround 7.1
- Micro antibruit détachable
- Éclairage RGB personnalisable
- Coussinets confortables
- Compatible PC/Console''',
                'is_featured': True,
            },
            {
                'name': 'Clavier Mécanique RGB',
                'category': 'Claviers Gaming',
                'price': 55000,
                'short_description': 'Clavier mécanique gaming avec switches bleus',
                'description': '''Clavier mécanique gaming:
- Switches mécaniques bleus
- Rétroéclairage RGB par touche
- Anti-ghosting complet
- Repose-poignet inclus
- Logiciel de personnalisation''',
                'is_featured': False,
            },
        ]

        for prod_data in products_data:
            product, created = Product.objects.get_or_create(
                name=prod_data['name'],
                defaults={
                    'slug': slugify(prod_data['name']),
                    'category': categories[prod_data['category']],
                    'price': prod_data['price'],
                    'short_description': prod_data['short_description'],
                    'description': prod_data['description'],
                    'is_featured': prod_data['is_featured'],
                    'status': 'active',
                }
            )
            if created:
                self.stdout.write(f'Created product: {product.name}')

                # Create variants for some products
                if 'Manette' in product.name:
                    variants_data = [
                        {'name': 'Noir', 'price_adjustment': 0},
                        {'name': 'Blanc', 'price_adjustment': 2000},
                        {'name': 'Rouge', 'price_adjustment': 3000},
                    ]
                    for var_data in variants_data:
                        ProductVariant.objects.create(
                            product=product,
                            name=var_data['name'],
                            price_adjustment=var_data['price_adjustment'],
                            is_active=True
                        )

                elif 'Gants' in product.name:
                    variants_data = [
                        {'name': 'Taille S', 'price_adjustment': 0},
                        {'name': 'Taille M', 'price_adjustment': 0},
                        {'name': 'Taille L', 'price_adjustment': 0},
                        {'name': 'Taille XL', 'price_adjustment': 1000},
                    ]
                    for var_data in variants_data:
                        ProductVariant.objects.create(
                            product=product,
                            name=var_data['name'],
                            price_adjustment=var_data['price_adjustment'],
                            is_active=True
                        )

        self.stdout.write(self.style.SUCCESS('Successfully populated shop with sample data!'))
        self.stdout.write(self.style.WARNING('Note: Add product images manually through the admin interface'))
