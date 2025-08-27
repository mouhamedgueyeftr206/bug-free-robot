"""
Gestionnaires de webhooks pour Shopify
Traitement des événements de commande, paiement et expédition
"""

import json
import hmac
import hashlib
import base64
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from .models import Order, ShopifyIntegration
from .shopify_utils import update_order_from_shopify_webhook, upsert_product_from_shopify_payload, deactivate_product_by_shopify_id

logger = logging.getLogger(__name__)

def verify_shopify_webhook(request, webhook_secret):
    """
    Vérifie l'authenticité d'un webhook Shopify
    """
    try:
        signature = request.headers.get('X-Shopify-Hmac-Sha256')
        if not signature:
            return False
        
        body = request.body
        digest = hmac.new(webhook_secret.encode('utf-8'), body, hashlib.sha256).digest()
        computed_signature = base64.b64encode(digest).decode('utf-8')
        return hmac.compare_digest(signature, computed_signature)
    except Exception as e:
        logger.error(f"Erreur lors de la vérification du webhook: {e}")
        return False

@csrf_exempt
@require_POST
def shopify_order_webhook(request):
    """
    Webhook pour les mises à jour de commandes Shopify
    """
    try:
        # Récupérer l'intégration Shopify active
        integration = ShopifyIntegration.objects.filter(is_active=True).first()
        if not integration:
            logger.error("Aucune intégration Shopify active")
            return HttpResponse("No active integration", status=400)
        
        # Vérifier la signature si un secret est configuré
        if integration.webhook_secret:
            if not verify_shopify_webhook(request, integration.webhook_secret):
                logger.error("Signature webhook invalide")
                return HttpResponse("Invalid signature", status=401)
        
        # Traiter les données du webhook
        webhook_data = json.loads(request.body)
        logger.info(f"Webhook Shopify reçu: {webhook_data.get('id')}")
        
        # Mettre à jour la commande locale
        update_order_from_shopify_webhook(webhook_data)
        
        return HttpResponse("OK", status=200)
        
    except json.JSONDecodeError:
        logger.error("Données JSON invalides dans le webhook")
        return HttpResponse("Invalid JSON", status=400)
    except Exception as e:
        logger.error(f"Erreur dans shopify_order_webhook: {e}")
        return HttpResponse("Internal error", status=500)

@csrf_exempt
@require_POST
def shopify_product_create_webhook(request):
    try:
        integration = ShopifyIntegration.objects.filter(is_active=True).first()
        if not integration:
            return HttpResponse("No active integration", status=400)
        if integration.webhook_secret and not verify_shopify_webhook(request, integration.webhook_secret):
            return HttpResponse("Invalid signature", status=401)
        data = json.loads(request.body)
        product = upsert_product_from_shopify_payload(data)
        logger.info(f"Produit créé/mis à jour: {product.name}")
        return HttpResponse("OK", status=200)
    except Exception as e:
        logger.error(f"Erreur product_create_webhook: {e}")
        return HttpResponse("Internal error", status=500)

@csrf_exempt
@require_POST
def shopify_product_update_webhook(request):
    try:
        integration = ShopifyIntegration.objects.filter(is_active=True).first()
        if not integration:
            return HttpResponse("No active integration", status=400)
        if integration.webhook_secret and not verify_shopify_webhook(request, integration.webhook_secret):
            return HttpResponse("Invalid signature", status=401)
        data = json.loads(request.body)
        product = upsert_product_from_shopify_payload(data)
        logger.info(f"Produit mis à jour: {product.name}")
        return HttpResponse("OK", status=200)
    except Exception as e:
        logger.error(f"Erreur product_update_webhook: {e}")
        return HttpResponse("Internal error", status=500)

@csrf_exempt
@require_POST
def shopify_product_delete_webhook(request):
    try:
        integration = ShopifyIntegration.objects.filter(is_active=True).first()
        if not integration:
            return HttpResponse("No active integration", status=400)
        if integration.webhook_secret and not verify_shopify_webhook(request, integration.webhook_secret):
            return HttpResponse("Invalid signature", status=401)
        data = json.loads(request.body)
        shopify_id = data.get('id')
        if shopify_id:
            deactivate_product_by_shopify_id(str(shopify_id))
        logger.info(f"Produit désactivé pour Shopify ID: {shopify_id}")
        return HttpResponse("OK", status=200)
    except Exception as e:
        logger.error(f"Erreur product_delete_webhook: {e}")
        return HttpResponse("Internal error", status=500)

@csrf_exempt
@require_POST
def shopify_fulfillment_webhook(request):
    """
    Webhook pour les mises à jour d'expédition Shopify
    """
    try:
        integration = ShopifyIntegration.objects.filter(is_active=True).first()
        if not integration:
            return HttpResponse("No active integration", status=400)
        
        if integration.webhook_secret:
            if not verify_shopify_webhook(request, integration.webhook_secret):
                return HttpResponse("Invalid signature", status=401)
        
        webhook_data = json.loads(request.body)
        order_id = str(webhook_data.get('order_id'))
        
        # Trouver la commande locale
        order = Order.objects.filter(shopify_order_id=order_id).first()
        if order:
            order.status = 'shipped'
            order.shopify_fulfillment_status = 'fulfilled'
            order.save()
            
            logger.info(f"Commande {order.order_number} marquée comme expédiée")
        
        return HttpResponse("OK", status=200)
        
    except Exception as e:
        logger.error(f"Erreur dans shopify_fulfillment_webhook: {e}")
        return HttpResponse("Internal error", status=500)

@csrf_exempt
@require_POST
def shopify_refund_webhook(request):
    """
    Webhook pour les remboursements Shopify
    """
    try:
        integration = ShopifyIntegration.objects.filter(is_active=True).first()
        if not integration:
            return HttpResponse("No active integration", status=400)
        
        if integration.webhook_secret:
            if not verify_shopify_webhook(request, integration.webhook_secret):
                return HttpResponse("Invalid signature", status=401)
        
        webhook_data = json.loads(request.body)
        order_id = str(webhook_data.get('order_id'))
        
        # Trouver la commande locale
        order = Order.objects.filter(shopify_order_id=order_id).first()
        if order:
            order.status = 'refunded'
            order.payment_status = 'refunded'
            order.save()
            
            # Mettre à jour la transaction CinetPay si elle existe
            if hasattr(order, 'cinetpay_transaction'):
                order.cinetpay_transaction.status = 'refunded'
                order.cinetpay_transaction.save()
            
            logger.info(f"Commande {order.order_number} remboursée")
        
        return HttpResponse("OK", status=200)
        
    except Exception as e:
        logger.error(f"Erreur dans shopify_refund_webhook: {e}")
        return HttpResponse("Internal error", status=500)