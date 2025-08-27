"""
Utilitaires pour l'intégration CinetPay
Gestion des paiements pour la boutique e-commerce (dropshipping)
"""

import requests
import json
import uuid
from django.conf import settings
from django.utils import timezone
from django.urls import reverse
from .models import ShopCinetPayTransaction, Order
import logging

logger = logging.getLogger(__name__)

class CinetPayAPI:
    def __init__(self):
        self.api_key = settings.CINETPAY_API_KEY
        self.site_id = settings.CINETPAY_SITE_ID
        self.secret_key = getattr(settings, 'CINETPAY_SECRET_KEY', '')
        self.base_url = 'https://api-checkout.cinetpay.com/v2'

    def initiate_payment(self, order, customer_data):
        """
        Initie un paiement CinetPay pour une commande boutique
        """
        try:
            # Générer un ID de transaction unique
            transaction_id = f"SHOP_{order.order_number}_{uuid.uuid4().hex[:8]}"
            
            # URLs de callback
            base_url = getattr(settings, 'BASE_URL', 'http://localhost:8000')
            return_url = f"{base_url}{reverse('shop_payment_success', args=[order.id])}"
            notify_url = f"{base_url}{reverse('shop_cinetpay_notification')}"
            cancel_url = f"{base_url}{reverse('shop_payment_failed', args=[order.id])}"
            
            # Données pour CinetPay
            payment_data = {
                'apikey': self.api_key,
                'site_id': self.site_id,
                'transaction_id': transaction_id,
                'amount': int(float(order.total_amount)),  # CinetPay attend un entier
                'currency': 'XOF',  # Devise par défaut
                'alternative_currency': 'XOF',
                'description': f'Commande BLIZZ #{order.order_number}',
                'return_url': return_url,
                'notify_url': notify_url,
                'cancel_url': cancel_url,
                'customer_id': str(order.user.id) if order.user else 'guest',
                'customer_name': customer_data.get('customer_name', order.customer_first_name),
                'customer_surname': customer_data.get('customer_surname', order.customer_last_name),
                'customer_email': customer_data.get('customer_email', order.customer_email),
                'customer_phone_number': customer_data.get('customer_phone_number', order.customer_phone),
                'customer_address': customer_data.get('customer_address', order.shipping_address_line1),
                'customer_city': customer_data.get('customer_city', order.shipping_city),
                'customer_country': customer_data.get('customer_country', order.shipping_country),
                'customer_state': customer_data.get('customer_state', order.shipping_state),
                'customer_zip_code': customer_data.get('customer_zip_code', order.shipping_postal_code),
            }
            
            # Appel à l'API CinetPay
            response = requests.post(
                f"{self.base_url}/payment",
                json=payment_data,
                headers={'Content-Type': 'application/json'},
                timeout=20
            )

            # Tenter de parser la réponse même si status != 200 pour récupérer le message d'erreur
            try:
                result = response.json()
            except Exception:
                result = {'code': str(response.status_code), 'message': response.text}
            
            # Si status HTTP indique erreur réseau/service, retour explicite
            if response.status_code >= 500:
                logger.error(f"Erreur serveur CinetPay: {response.status_code} - {response.text}")
                return {'success': False, 'error': 'Erreur de connexion au service de paiement'}
            
            if result.get('code') == '201':
                # Succès - créer la transaction locale
                cinetpay_transaction = ShopCinetPayTransaction.objects.create(
                    order=order,
                    cinetpay_transaction_id=transaction_id,
                    payment_url=result['data']['payment_url'],
                    payment_token=result['data'].get('payment_token', ''),
                    customer_name=customer_data.get('customer_name', order.customer_first_name),
                    customer_surname=customer_data.get('customer_surname', order.customer_last_name),
                    customer_phone_number=customer_data.get('customer_phone_number', order.customer_phone),
                    customer_email=customer_data.get('customer_email', order.customer_email),
                    customer_country=customer_data.get('customer_country', order.shipping_country),
                    amount=order.total_amount,
                    currency='XOF',
                    status='pending'
                )
                
                logger.info(f"Paiement CinetPay initié: {transaction_id}")
                return {
                    'success': True,
                    'payment_url': result['data']['payment_url'],
                    'transaction_id': transaction_id,
                    'cinetpay_transaction': cinetpay_transaction
                }
            else:
                # Normaliser quelques erreurs fréquentes
                code = (result.get('code') or '').upper()
                error_msg = result.get('message', 'Erreur inconnue')
                if code == 'ERROR_AMOUNT_TOO_LOW':
                    error_msg = "Montant trop bas pour CinetPay. Augmentez le total (ex: > 100 XOF)."
                logger.error(f"Erreur CinetPay: {error_msg}")
                return {
                    'success': False,
                    'error': error_msg
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur de requête CinetPay: {e}")
            return {
                'success': False,
                'error': 'Erreur de connexion au service de paiement'
            }
        except Exception as e:
            logger.error(f"Erreur inattendue CinetPay: {e}")
            return {
                'success': False,
                'error': 'Erreur interne du service de paiement'
            }

    def verify_payment(self, transaction_id):
        """
        Vérifie le statut d'un paiement CinetPay
        """
        try:
            verification_data = {
                'apikey': self.api_key,
                'site_id': self.site_id,
                'transaction_id': transaction_id
            }
            
            response = requests.post(
                f"{self.base_url}/payment/check",
                json=verification_data,
                headers={'Content-Type': 'application/json'}
            )
            
            response.raise_for_status()
            result = response.json()
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification: {e}")
            return None

def handle_cinetpay_notification(notification_data):
    """
    Traite une notification CinetPay pour la boutique
    """
    try:
        transaction_id = notification_data.get('cpm_trans_id')
        if not transaction_id:
            logger.error("ID de transaction manquant dans la notification")
            return False
        
        # Trouver la transaction locale
        cinetpay_transaction = ShopCinetPayTransaction.objects.filter(
            cinetpay_transaction_id=transaction_id
        ).first()
        
        if not cinetpay_transaction:
            logger.error(f"Transaction CinetPay non trouvée: {transaction_id}")
            return False
        
        order = cinetpay_transaction.order
        
        # Vérifier le statut du paiement
        cinetpay_api = CinetPayAPI()
        verification_result = cinetpay_api.verify_payment(transaction_id)
        
        if not verification_result:
            logger.error(f"Impossible de vérifier le paiement: {transaction_id}")
            return False
        
        payment_status = verification_result.get('data', {}).get('payment_status')
        
        if payment_status == 'ACCEPTED':
            # Paiement réussi
            cinetpay_transaction.status = 'completed'
            cinetpay_transaction.completed_at = timezone.now()
            cinetpay_transaction.save()
            
            # Mettre à jour la commande
            order.payment_status = 'paid'
            order.status = 'processing'
            order.save()
            
            # Créer la commande sur Shopify
            from .shopify_utils import create_shopify_order_from_blizz_order, mark_order_as_paid_in_shopify
            
            try:
                shopify_order = create_shopify_order_from_blizz_order(order)
                if shopify_order:
                    # Marquer comme payée dans Shopify
                    mark_order_as_paid_in_shopify(order)
                    logger.info(f"Commande transférée vers Shopify: {order.order_number}")
                else:
                    logger.error(f"Échec de création commande Shopify pour: {order.order_number}")
            except Exception as e:
                logger.error(f"Erreur lors du transfert Shopify: {e}")
            
            return True
            
        elif payment_status == 'REFUSED':
            # Paiement échoué
            cinetpay_transaction.status = 'failed'
            cinetpay_transaction.save()
            
            order.payment_status = 'failed'
            order.status = 'cancelled'
            order.save()
            
            logger.info(f"Paiement échoué pour: {transaction_id}")
            return True
        
        else:
            logger.warning(f"Statut de paiement non géré: {payment_status}")
            return False
            
    except Exception as e:
        logger.error(f"Erreur lors du traitement de la notification: {e}")
        return False

def convert_currency_for_cinetpay(amount, from_currency='EUR', to_currency='XOF'):
    """
    Convertit les devises pour CinetPay
    Taux de change approximatifs (à mettre à jour avec une API de change)
    """
    exchange_rates = {
        'EUR': {
            'XOF': 655.957,  # 1 EUR = 655.957 XOF
            'XAF': 655.957,  # 1 EUR = 655.957 XAF
            'GNF': 9000,     # 1 EUR = 9000 GNF (approximatif)
            'USD': 1.1,      # 1 EUR = 1.1 USD (approximatif)
        },
        'USD': {
            'XOF': 596.32,   # 1 USD = 596.32 XOF
            'XAF': 596.32,   # 1 USD = 596.32 XAF
            'GNF': 8200,     # 1 USD = 8200 GNF (approximatif)
            'EUR': 0.91,     # 1 USD = 0.91 EUR (approximatif)
        }
    }
    
    if from_currency == to_currency:
        return float(amount)
    
    if from_currency in exchange_rates and to_currency in exchange_rates[from_currency]:
        rate = exchange_rates[from_currency][to_currency]
        converted_amount = float(amount) * rate
        return round(converted_amount, 2)
    
    # Fallback: retourner le montant original
    logger.warning(f"Conversion non supportée: {from_currency} -> {to_currency}")
    return float(amount)

def get_supported_countries():
    """
    Retourne la liste des pays supportés par CinetPay
    """
    return [
        ('CI', 'Côte d\'Ivoire'),
        ('SN', 'Sénégal'),
        ('BF', 'Burkina Faso'),
        ('ML', 'Mali'),
        ('NE', 'Niger'),
        ('TG', 'Togo'),
        ('BJ', 'Bénin'),
        ('GN', 'Guinée'),
        ('CM', 'Cameroun'),
        ('CD', 'RD Congo'),
    ]

def get_currency_for_country(country_code):
    """
    Retourne la devise appropriée selon le pays
    """
    currency_map = {
        'CI': 'XOF',  # Côte d'Ivoire
        'SN': 'XOF',  # Sénégal
        'BF': 'XOF',  # Burkina Faso
        'ML': 'XOF',  # Mali
        'NE': 'XOF',  # Niger
        'TG': 'XOF',  # Togo
        'BJ': 'XOF',  # Bénin
        'GN': 'GNF',  # Guinée
        'CM': 'XAF',  # Cameroun
        'CD': 'CDF',  # RD Congo
    }
    
    return currency_map.get(country_code, 'XOF')