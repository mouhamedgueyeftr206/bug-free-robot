"""
Utilitaires pour l'intégration Shopify
Gestion des produits, commandes et webhooks
"""

import requests
import json
import os
from urllib.parse import urlparse
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify
from django.core.files.base import ContentFile
from decimal import Decimal
from .models import ShopifyIntegration, Product, Order, OrderItem, ProductCategory, ProductImage
import logging

logger = logging.getLogger(__name__)

class ShopifyAPI:
    def __init__(self, shop_name=None, access_token=None, shop_url=None):
        """
        Initialise l'API Shopify
        """
        if (shop_name or shop_url) and access_token:
            self.shop_name = shop_name
            self.shop_url = shop_url
            self.access_token = access_token
        else:
            # Récupérer depuis la base de données
            integration = ShopifyIntegration.objects.filter(is_active=True).order_by('-updated_at').first()
            if not integration:
                raise ValueError("Aucune intégration Shopify active trouvée")
            self.shop_name = integration.shop_name
            self.shop_url = integration.shop_url
            self.access_token = integration.access_token
        
        base_host = None
        if self.shop_url:
            # shop_url fourni (ex: https://votre-boutique.myshopify.com)
            base_host = self.shop_url.rstrip('/')
        else:
            base_host = f"https://{self.shop_name}.myshopify.com"
        self.base_url = f"{base_host}/admin/api/2023-10"
        self.headers = {
            'X-Shopify-Access-Token': self.access_token,
            'Content-Type': 'application/json'
        }

    def _make_request(self, method, endpoint, data=None):
        """
        Effectue une requête vers l'API Shopify
        """
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data)
            elif method == 'PUT':
                response = requests.put(url, headers=self.headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=self.headers)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur API Shopify: {e}")
            raise

    def get_products(self, limit=50):
        """
        Récupère les produits depuis Shopify
        """
        return self._make_request('GET', f'products.json?limit={limit}')

    def get_product(self, product_id):
        """
        Récupère un produit spécifique
        """
        return self._make_request('GET', f'products/{product_id}.json')

    def create_order(self, order_data):
        """
        Crée une commande sur Shopify
        """
        return self._make_request('POST', 'orders.json', {'order': order_data})

    def get_order(self, order_id):
        """
        Récupère une commande spécifique
        """
        return self._make_request('GET', f'orders/{order_id}.json')

    def update_order(self, order_id, order_data):
        """
        Met à jour une commande
        """
        return self._make_request('PUT', f'orders/{order_id}.json', {'order': order_data})

    def create_fulfillment(self, order_id, fulfillment_data):
        """
        Crée un fulfillment (expédition) pour une commande
        """
        return self._make_request('POST', f'orders/{order_id}/fulfillments.json', {'fulfillment': fulfillment_data})

def sync_products_from_shopify():
    """
    Synchronise les produits depuis Shopify vers la base de données locale
    """
    try:
        shopify_api = ShopifyAPI()
        products_data = shopify_api.get_products(limit=250)
        
        synced_count = 0
        
        for product_data in products_data.get('products', []):
            # Déterminer la catégorie
            category_name = product_data.get('product_type') or 'Divers'
            category, _ = ProductCategory.objects.get_or_create(
                name=category_name,
                defaults={
                    'slug': slugify(category_name)[:100],
                    'description': '',
                    'is_active': True,
                }
            )

            # Déterminer le prix initial (première variante si dispo)
            first_variant = None
            if product_data.get('variants'):
                if len(product_data['variants']) > 0:
                    first_variant = product_data['variants'][0]
            price_value = Decimal(str(first_variant['price'])) if first_variant and first_variant.get('price') not in (None, '') else Decimal('0.00')

            # Statut local
            shopify_status = product_data.get('status') or ''
            local_status = 'active' if shopify_status == 'active' else 'inactive'

            # Créer ou mettre à jour le produit
            product, created = Product.objects.update_or_create(
                shopify_product_id=str(product_data['id']),
                defaults={
                    'name': product_data.get('title') or 'Sans titre',
                    'slug': product_data.get('handle') or slugify(product_data.get('title') or f"prod-{product_data.get('id')}")[:200],
                    'description': product_data.get('body_html') or '',
                    'shopify_handle': product_data.get('handle') or '',
                    'status': local_status,
                    'updated_at': timezone.now(),
                    'category': category,
                    'price': price_value,
                }
            )

            # Enrichir avec variant_id si dispo
            if first_variant:
                product.shopify_variant_id = str(first_variant.get('id')) if first_variant.get('id') else None
                product.save(update_fields=['shopify_variant_id'])

            # Images
            try:
                _save_product_images(product, product_data)
            except Exception as e:
                logger.error(f"Erreur enregistrement images: {e}")

            synced_count += 1
            
        logger.info(f"Synchronisation terminée: {synced_count} produits traités")
        return synced_count
        
    except Exception as e:
        logger.error(f"Erreur lors de la synchronisation: {e}")
        raise

def _download_image_to_bytes(image_url: str):
    try:
        resp = requests.get(image_url, timeout=20)
        resp.raise_for_status()
        # Déterminer un nom de fichier
        parsed = urlparse(image_url)
        base_name = os.path.basename(parsed.path)
        if not base_name:
            base_name = 'image.jpg'
        return base_name, resp.content
    except Exception as e:
        logger.error(f"Téléchargement image échoué ({image_url}): {e}")
        return None

def _save_product_images(product: Product, product_data: dict) -> None:
    """Remplace les images d'un produit par celles de Shopify et définit l'image à la une."""
    images = product_data.get('images') or []
    if not images:
        return

    # Nettoyer les anciennes images
    try:
        product.images.all().delete()
    except Exception:
        pass

    # Télécharger et enregistrer
    for idx, img in enumerate(images):
        src = img.get('src')
        if not src:
            continue
        downloaded = _download_image_to_bytes(src)
        if not downloaded:
            continue
        filename, raw_bytes = downloaded
        try:
            # Image galerie
            gallery = ProductImage(product=product, order=idx, alt_text=img.get('alt') or '')
            gallery.image.save(filename, ContentFile(raw_bytes), save=True)
            if idx == 0:
                # Image principale
                product.featured_image.save(filename, ContentFile(raw_bytes), save=True)
        except Exception as e:
            logger.error(f"Échec sauvegarde image produit: {e}")


def upsert_product_from_shopify_payload(product_data: dict) -> Product:
    """
    Crée ou met à jour un produit local à partir du payload Shopify (webhook products/create|update)
    """
    # Catégorie depuis product_type (fallback Divers)
    category_name = product_data.get('product_type') or 'Divers'
    category, _ = ProductCategory.objects.get_or_create(
        name=category_name,
        defaults={
            'slug': slugify(category_name)[:100],
            'description': '',
            'is_active': True,
        }
    )

    # Prix depuis première variante
    first_variant = None
    if product_data.get('variants'):
        if len(product_data['variants']) > 0:
            first_variant = product_data['variants'][0]
    price_value = Decimal(str(first_variant['price'])) if first_variant and first_variant.get('price') not in (None, '') else Decimal('0.00')

    # Statut
    shopify_status = product_data.get('status') or ''
    local_status = 'active' if shopify_status == 'active' else 'inactive'

    product, _ = Product.objects.update_or_create(
        shopify_product_id=str(product_data['id']),
        defaults={
            'name': product_data.get('title') or 'Sans titre',
            'slug': (product_data.get('handle') or slugify(product_data.get('title') or f"prod-{product_data.get('id')}")[:200]),
            'description': product_data.get('body_html') or '',
            'shopify_handle': product_data.get('handle') or '',
            'status': local_status,
            'updated_at': timezone.now(),
            'category': category,
            'price': price_value,
        }
    )

    if first_variant and first_variant.get('id'):
        product.shopify_variant_id = str(first_variant['id'])
        product.save(update_fields=['shopify_variant_id'])

    # Images via webhook
    try:
        _save_product_images(product, product_data)
    except Exception as e:
        logger.error(f"Erreur images webhook: {e}")

    return product

def deactivate_product_by_shopify_id(shopify_product_id: str) -> bool:
    """Marque un produit comme inactif lorsqu'il est supprimé dans Shopify."""
    prod = Product.objects.filter(shopify_product_id=str(shopify_product_id)).first()
    if not prod:
        return False
    prod.status = 'inactive'
    prod.save(update_fields=['status'])
    return True

def create_shopify_order_from_blizz_order(order):
    """
    Crée une commande Shopify à partir d'une commande BLIZZ
    """
    try:
        shopify_api = ShopifyAPI()
        
        # Préparer les données de la commande
        line_items = []
        for item in order.items.all():
            line_item = {
                'variant_id': int(item.product.shopify_variant_id) if item.product.shopify_variant_id else None,
                'quantity': item.quantity,
                'price': str(item.product_price)
            }
            
            # Si pas de variant_id, utiliser le product_id
            if not line_item['variant_id'] and item.product.shopify_product_id:
                # Récupérer les variantes du produit
                product_data = shopify_api.get_product(item.product.shopify_product_id)
                if product_data.get('product', {}).get('variants'):
                    line_item['variant_id'] = product_data['product']['variants'][0]['id']
            
            line_items.append(line_item)
        
        # Données de la commande Shopify
        shopify_order_data = {
            'email': order.customer_email,
            'phone': order.customer_phone,
            'line_items': line_items,
            'shipping_address': {
                'first_name': order.customer_first_name,
                'last_name': order.customer_last_name,
                'address1': order.shipping_address_line1,
                'address2': order.shipping_address_line2 or '',
                'city': order.shipping_city,
                'province': order.shipping_state,
                'country': order.shipping_country,
                'zip': order.shipping_postal_code,
                'phone': order.customer_phone,
            },
            'billing_address': {
                'first_name': order.customer_first_name,
                'last_name': order.customer_last_name,
                'address1': order.shipping_address_line1,
                'address2': order.shipping_address_line2 or '',
                'city': order.shipping_city,
                'province': order.shipping_state,
                'country': order.shipping_country,
                'zip': order.shipping_postal_code,
                'phone': order.customer_phone,
            },
            'financial_status': 'pending',
            'fulfillment_status': None,
            'tags': 'BLIZZ-Dropshipping',
            'note': f'Commande BLIZZ #{order.order_number}',
            'source_name': 'BLIZZ',
        }
        
        # Créer la commande sur Shopify
        response = shopify_api.create_order(shopify_order_data)
        
        if response.get('order'):
            shopify_order = response['order']
            
            # Mettre à jour la commande locale
            order.shopify_order_id = str(shopify_order['id'])
            order.shopify_order_number = shopify_order.get('order_number', '')
            order.status = 'processing'
            order.save()
            
            # Mettre à jour les items avec les IDs Shopify
            for i, item in enumerate(order.items.all()):
                if i < len(shopify_order.get('line_items', [])):
                    shopify_line_item = shopify_order['line_items'][i]
                    item.shopify_line_item_id = str(shopify_line_item['id'])
                    item.save()
            
            logger.info(f"Commande Shopify créée: {shopify_order['id']} pour commande BLIZZ {order.order_number}")
            return shopify_order
        
        else:
            raise Exception("Échec de création de commande Shopify")
            
    except Exception as e:
        logger.error(f"Erreur lors de la création de commande Shopify: {e}")
        raise

def update_order_from_shopify_webhook(webhook_data):
    """
    Met à jour une commande locale à partir d'un webhook Shopify
    """
    try:
        shopify_order_id = str(webhook_data.get('id'))
        
        # Trouver la commande locale
        order = Order.objects.filter(shopify_order_id=shopify_order_id).first()
        if not order:
            logger.warning(f"Commande locale non trouvée pour Shopify ID: {shopify_order_id}")
            return
        
        # Mettre à jour le statut
        shopify_status = webhook_data.get('fulfillment_status')
        if shopify_status == 'fulfilled':
            order.status = 'shipped'
            order.shipped_at = timezone.now()
        elif shopify_status == 'partial':
            order.status = 'processing'
        
        # Mettre à jour le statut financier
        financial_status = webhook_data.get('financial_status')
        if financial_status == 'paid':
            order.payment_status = 'paid'
        elif financial_status == 'refunded':
            order.payment_status = 'refunded'
            order.status = 'refunded'
        
        order.shopify_fulfillment_status = shopify_status
        order.save()
        
        logger.info(f"Commande {order.order_number} mise à jour depuis Shopify")
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour depuis webhook: {e}")

def get_shopify_product_info(product_id):
    """
    Récupère les informations d'un produit Shopify
    """
    try:
        shopify_api = ShopifyAPI()
        response = shopify_api.get_product(product_id)
        return response.get('product')
    except Exception as e:
        logger.error(f"Erreur lors de la récupération du produit Shopify: {e}")
        return None

def mark_order_as_paid_in_shopify(order):
    """
    Marque une commande comme payée dans Shopify
    """
    try:
        if not order.shopify_order_id:
            logger.warning(f"Pas d'ID Shopify pour la commande {order.order_number}")
            return False
        
        shopify_api = ShopifyAPI()
        
        # Mettre à jour le statut financier
        update_data = {
            'financial_status': 'paid',
            'tags': 'BLIZZ-Dropshipping,Paid-via-CinetPay'
        }
        
        response = shopify_api.update_order(order.shopify_order_id, update_data)
        
        if response.get('order'):
            logger.info(f"Commande Shopify {order.shopify_order_id} marquée comme payée")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour du paiement Shopify: {e}")
        return False