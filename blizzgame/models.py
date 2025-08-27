import uuid
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator
from django.utils import timezone
import json

# Modèles Highlights
class Highlight(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='highlights')
    video = models.FileField(upload_to='highlights_videos/')
    caption = models.TextField(max_length=500, blank=True)
    hashtags = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    views_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(hours=48)
        super().save(*args, **kwargs)
    
    @property
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @property
    def time_remaining(self):
        if self.is_expired:
            return None
        return self.expires_at - timezone.now()
    
    @property
    def appreciations_count(self):
        return self.appreciations.count()
    
    @property
    def comments_count(self):
        return self.comments.count()
    
    def get_appreciation_counts_by_level(self):
        """Retourne un dictionnaire avec le nombre d'appréciations par niveau"""
        counts = {}
        for level in range(1, 7):
            counts[level] = self.appreciations.filter(appreciation_level=level).count()
        return counts
    
    def __str__(self):
        return f"Highlight by {self.author.username} - {self.created_at}"

class HighlightAppreciation(models.Model):
    """Système d'appréciation avec 6 niveaux d'émotions"""
    APPRECIATION_CHOICES = [
        (1, 'Extrêmement nul'),
        (2, 'Pas terrible'),
        (3, 'Moyen'),
        (4, 'Bien'),
        (5, 'Très bien'),
        (6, 'Extraordinaire'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    highlight = models.ForeignKey(Highlight, on_delete=models.CASCADE, related_name='appreciations')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='highlight_appreciations')
    appreciation_level = models.IntegerField(choices=APPRECIATION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['highlight', 'user']
    
    def __str__(self):
        return f"{self.user.username} - Niveau {self.appreciation_level} sur {self.highlight.id}"
    
    @property
    def score_impact(self):
        """Retourne l'impact sur le score de l'auteur"""
        score_impacts = {
            1: -10,  # Extrêmement nul
            2: -4,   # Pas terrible
            3: 2,    # Moyen
            4: 4,    # Bien
            5: 6,    # Très bien
            6: 10,   # Extraordinaire
        }
        return score_impacts.get(self.appreciation_level, 0)

class HighlightComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    highlight = models.ForeignKey(Highlight, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='highlight_comments')
    content = models.TextField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.highlight.id}"

class HighlightView(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    highlight = models.ForeignKey(Highlight, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='highlight_views', null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    view_duration = models.FloatField(default=0.0, help_text="View duration in seconds")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['highlight', 'user']
    
    def __str__(self):
        return f"View on {self.highlight.id} by {self.user.username if self.user else 'Anonymous'} ({self.view_duration}s)"

class HighlightShare(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    highlight = models.ForeignKey(Highlight, on_delete=models.CASCADE, related_name='shares')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='highlight_shares')
    shared_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_highlight_shares', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} shared {self.highlight.id}"

class UserSubscription(models.Model):
    """Système d'abonnement pour les Highlights (remplace les demandes d'amis)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    subscriber = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    subscribed_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscribers')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['subscriber', 'subscribed_to']
        constraints = [
            models.CheckConstraint(
                check=~models.Q(subscriber=models.F('subscribed_to')),
                name='no_self_subscription'
            )
        ]
    
    def __str__(self):
        return f"{self.subscriber.username} subscribed to {self.subscribed_to.username}"

# Modèles existants
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    id_user = models.IntegerField()
    bio = models.TextField(blank=True)
    profileimg = models.ImageField(upload_to='profile_images', default='default_profile.png', blank=True, null=True)
    location = models.CharField(max_length=100, blank=True)
    banner = models.ImageField(upload_to='banner_images', default='default_banner.png', blank=True, null=True)
    favorite_games = models.JSONField(default=list, blank=True, help_text="Liste des jeux favoris de l'utilisateur")
    
    # Champs pour le système de réputation
    score = models.IntegerField(default=0, help_text="Score basé sur les appréciations des Highlights")
    appreciation_count = models.IntegerField(default=0, help_text="Nombre total d'appréciations reçues")

    @property
    def friends_count(self):
        """Compte le nombre d'amis (abonnements mutuels)"""
        user_subscriptions = set(self.user.subscriptions.values_list('subscribed_to_id', flat=True))
        user_subscribers = set(self.user.subscribers.values_list('subscriber_id', flat=True))
        return len(user_subscriptions.intersection(user_subscribers))
    
    @property
    def subscribers_count(self):
        """Compte le nombre d'abonnés"""
        return self.user.subscribers.count()
    
    @property
    def subscriptions_count(self):
        """Compte le nombre d'abonnements"""
        return self.user.subscriptions.count()

    GAME_CHOICES = [
        ('FreeFire', 'FreeFire'),
        ('PUBG', 'PUBG Mobile'),
        ('COD', 'Call of Duty Mobile'),
        ('efootball', 'eFootball Mobile'),
        ('fc25', 'FC25 Mobile'),
        ('bloodstrike', 'Bloodstrike'),
        ('other', 'Autre'),
    ]

    def __str__(self):
        return self.user.username

    @property
    def appreciation_percentage(self):
        """Calcule le pourcentage d'appréciations positives (niveaux 4-6)"""
        if self.appreciation_count == 0:
            return 0.0
        
        # Compter les appréciations positives (niveaux 4-6)
        positive_appreciations = HighlightAppreciation.objects.filter(
            highlight__author=self.user
        ).filter(appreciation_level__gte=4).count()
        
        return round((positive_appreciations / self.appreciation_count) * 100, 1)
    
    def update_score_from_appreciation(self, appreciation_level):
        """Met à jour le score basé sur une nouvelle appréciation"""
        score_impacts = {
            1: -10,  # Extrêmement nul
            2: -4,   # Pas terrible
            3: 2,    # Moyen
            4: 4,    # Bien
            5: 6,    # Très bien
            6: 10,   # Extraordinaire
        }
        
        impact = score_impacts.get(appreciation_level, 0)
        self.score += impact
        self.appreciation_count += 1
        self.save()

    @property
    def appreciation_level_counts(self):
        """Retourne un dict {1..6: count} des appréciations reçues par niveau pour tous les highlights de l'utilisateur."""
        counts = {level: 0 for level in range(1, 7)}
        qs = HighlightAppreciation.objects.filter(highlight__author=self.user)
        for level in range(1, 7):
            counts[level] = qs.filter(appreciation_level=level).count()
        return counts

    @property
    def appreciation_level_percentages(self):
        """Retourne un dict {1..6: percent} basé sur appreciation_count (0 si aucun)."""
        total = self.appreciation_count or 0
        counts = self.appreciation_level_counts
        if total == 0:
            return {level: 0.0 for level in range(1, 7)}
        return {level: round((counts[level] / total) * 100, 1) for level in counts}

class Post(models.Model):
    GAME_CHOICES = [
        ('FreeFire', 'FreeFire'),
        ('PUBG', 'PUBG Mobile'),
        ('COD', 'Call of Duty Mobile'),
        ('efootball', 'eFootball Mobile'),
        ('fc25', 'FC25 Mobile'),
        ('bloodstrike', 'Bloodstrike'),
        ('other', 'Autre'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.CharField(max_length=100)
    author = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    title = models.CharField(max_length=200, default='sans nom')
    banner = models.ImageField(upload_to='post_banners', default='def_img.png')
    caption = models.TextField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    no_of_likes = models.IntegerField(default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MaxValueValidator(999999.99)])
    email = models.EmailField(default='sans email')
    password = models.CharField(max_length=254, default='sans password')
    is_sold = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    game_type = models.CharField(max_length=50, choices=GAME_CHOICES, default='other')
    custom_game_name = models.CharField(max_length=100, blank=True, null=True)
    coins = models.CharField(max_length=100, default='')
    level = models.CharField(max_length=50, default='')

    def get_game_display_name(self):
        if self.game_type == 'other' and self.custom_game_name:
            return self.custom_game_name
        else:
            return dict(self.GAME_CHOICES).get(self.game_type, 'Autre')

    @property
    def main_image(self):
        return self.banner

    @property
    def has_banner(self):
        return bool(self.banner and self.banner.name != 'def_img.png')

    @property
    def time_since_created(self):
        from django.utils.timesince import timesince
        return timesince(self.created_at)

    @property
    def is_in_transaction(self):
        return self.transactions.filter(status__in=['pending', 'processing']).exists()

    def __str__(self):
        return self.title

class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='post_images')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        constraints = [
            models.UniqueConstraint(fields=['post', 'order'], name='unique_image_order'),
            models.CheckConstraint(check=models.Q(order__lt=10), name='max_images_per_post'),
        ]

class PostVideo(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='videos')
    video = models.FileField(upload_to='post_videos/')

# Modèles de transaction existants
class Transaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
        ('disputed', 'Litigieuse'),
        ('refunded', 'Remboursée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchases')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sales')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    security_period_end = models.DateTimeField(null=True, blank=True)
    account_verified_before = models.BooleanField(default=False)
    account_verified_after = models.BooleanField(default=False)

    def __str__(self):
        return f"Transaction {self.id} - {self.buyer.username} -> {self.seller.username}"

# Modèles CinetPay existants
class CinetPayTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending_payment', 'Paiement en attente'),
        ('payment_received', 'Paiement reçu'),
        ('in_escrow', 'En séquestre'),
        ('escrow_released', 'Séquestre libéré'),
        ('escrow_refunded', 'Séquestre remboursé'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
        ('cancelled', 'Annulé'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='cinetpay_transaction')
    customer_id = models.CharField(max_length=100)
    customer_name = models.CharField(max_length=100)
    customer_surname = models.CharField(max_length=100)
    customer_phone_number = models.CharField(max_length=20)
    customer_email = models.EmailField()
    customer_address = models.CharField(max_length=200)
    customer_city = models.CharField(max_length=100)
    customer_country = models.CharField(max_length=2)
    customer_state = models.CharField(max_length=2)
    customer_zip_code = models.CharField(max_length=10)
    seller_phone_number = models.CharField(max_length=20)
    seller_country = models.CharField(max_length=2)
    seller_operator = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='XOF')
    platform_commission = models.DecimalField(max_digits=10, decimal_places=2)
    seller_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_payment')
    cinetpay_transaction_id = models.CharField(max_length=100, unique=True)
    payment_url = models.URLField(null=True, blank=True)
    payment_token = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    payment_received_at = models.DateTimeField(null=True, blank=True)
    escrow_released_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"CinetPay {self.cinetpay_transaction_id} - {self.status}"

# Modèles Shopify corrigés
class ShopifyIntegration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    shop_name = models.CharField(max_length=100)
    shop_url = models.URLField()
    access_token = models.CharField(max_length=255)
    webhook_secret = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Shopify - {self.shop_name}"

class ProductCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='category_images/', null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='subcategories')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = 'Product Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(models.Model):
    STATUS_CHOICES = [
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('out_of_stock', 'Rupture de stock'),
        ('discontinued', 'Arrêté'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    category = models.ForeignKey(ProductCategory, on_delete=models.CASCADE, related_name='products')
    description = models.TextField()
    short_description = models.CharField(max_length=500, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    compare_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tags = models.JSONField(default=list, blank=True)
    featured_image = models.ImageField(upload_to='product_images/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    is_featured = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    
    # Champs Shopify
    shopify_product_id = models.CharField(max_length=100, null=True, blank=True)
    shopify_variant_id = models.CharField(max_length=100, null=True, blank=True)
    shopify_handle = models.CharField(max_length=200, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'is_featured']),
            models.Index(fields=['category', 'status']),
        ]

    def __str__(self):
        return self.name

    def get_main_image(self):
        if self.featured_image:
            return self.featured_image
        first_image = self.images.first()
        return first_image.image if first_image else None

class ProductImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='product_images/')
    alt_text = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order']

class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    name = models.CharField(max_length=100)  # Ex: "Couleur", "Taille"
    value = models.CharField(max_length=100)  # Ex: "Rouge", "L"
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shopify_variant_id = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['product', 'name', 'value']

    def __str__(self):
        return f"{self.product.name} - {self.name}: {self.value}"

    def get_final_price(self):
        return self.product.price + self.price_adjustment

# Modèles de panier et commande
class Cart(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='carts', null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total_price(self):
        return sum(item.get_total_price() for item in self.items.all())

    def get_total_items(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def is_empty(self):
        return not self.items.exists()

    def __str__(self):
        return f"Cart {self.id} - {self.user.username if self.user else 'Anonymous'}"

class CartItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['cart', 'product', 'variant']

    def get_total_price(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours de traitement'),
        ('shipped', 'Expédiée'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
        ('refunded', 'Remboursée'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('paid', 'Payée'),
        ('failed', 'Échouée'),
        ('refunded', 'Remboursée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='shop_orders', null=True, blank=True)
    order_number = models.CharField(max_length=20, unique=True)
    
    # Informations client
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    customer_first_name = models.CharField(max_length=100)
    customer_last_name = models.CharField(max_length=100)
    
    # Adresse de livraison
    shipping_address_line1 = models.CharField(max_length=200)
    shipping_address_line2 = models.CharField(max_length=200, blank=True)
    shipping_city = models.CharField(max_length=100)
    shipping_state = models.CharField(max_length=100)
    shipping_postal_code = models.CharField(max_length=20)
    shipping_country = models.CharField(max_length=2)
    
    # Montants
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Statuts
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Intégration Shopify
    shopify_order_id = models.CharField(max_length=100, null=True, blank=True)
    shopify_order_number = models.CharField(max_length=50, null=True, blank=True)
    shopify_fulfillment_status = models.CharField(max_length=50, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.order_number}"

    def generate_order_number(self):
        """Génère un numéro de commande unique"""
        import random
        import string
        while True:
            number = 'BLZ' + ''.join(random.choices(string.digits, k=8))
            if not Order.objects.filter(order_number=number).exists():
                return number

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)

class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, null=True, blank=True)
    product_name = models.CharField(max_length=200)
    product_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    shopify_line_item_id = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.quantity}x {self.product_name}"

# Transaction CinetPay pour la boutique (dropshipping)
class ShopCinetPayTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminée'),
        ('failed', 'Échouée'),
        ('cancelled', 'Annulée'),
        ('refunded', 'Remboursée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='cinetpay_transaction')
    
    # ID de transaction CinetPay
    cinetpay_transaction_id = models.CharField(max_length=100, unique=True)
    payment_url = models.URLField(null=True, blank=True)
    payment_token = models.CharField(max_length=255, null=True, blank=True)
    
    # Informations client pour CinetPay
    customer_name = models.CharField(max_length=100)
    customer_surname = models.CharField(max_length=100)
    customer_phone_number = models.CharField(max_length=20)
    customer_email = models.EmailField()
    customer_country = models.CharField(max_length=2)
    
    # Montants
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='XOF')
    
    # Statut et timestamps
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Shop CinetPay {self.cinetpay_transaction_id} - {self.order.order_number}"

# Modèles de réputation et autres (existants)
class UserReputation(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='reputation')
    
    # Métriques vendeur
    seller_total_transactions = models.IntegerField(default=0)
    seller_successful_transactions = models.IntegerField(default=0)
    seller_failed_transactions = models.IntegerField(default=0)
    seller_fraudulent_transactions = models.IntegerField(default=0)
    seller_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    seller_badge = models.CharField(max_length=50, default='novice')
    
    # Métriques acheteur
    buyer_total_transactions = models.IntegerField(default=0)
    buyer_successful_transactions = models.IntegerField(default=0)
    buyer_failed_transactions = models.IntegerField(default=0)
    buyer_disputed_transactions = models.IntegerField(default=0)
    buyer_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    buyer_badge = models.CharField(max_length=50, default='novice')
    
    # Timestamps
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_seller_badge(self):
        from .badge_config import get_seller_badge
        return get_seller_badge(float(self.seller_score))

    def update_reputation(self):
        from .badge_config import get_seller_badge
        
        # Calcul du score vendeur avec facteur de confiance
        if self.seller_total_transactions > 0:
            base_score = (self.seller_successful_transactions / self.seller_total_transactions) * 100
            confidence_factor = min(self.seller_total_transactions / 10, 1.0)
            volume_adjusted_score = base_score * confidence_factor
            
            # Obtenir le badge potentiel et son facteur
            potential_badge = get_seller_badge(volume_adjusted_score)
            badge_factor = potential_badge.get('factor', 1.0) if potential_badge else 1.0
            
            # Score final avec facteur de badge
            self.seller_score = volume_adjusted_score * badge_factor
            
            # Badge final
            final_badge = get_seller_badge(self.seller_score)
            self.seller_badge = final_badge['level'] if final_badge else 'bronze'
        
        self.save()

    def __str__(self):
        return f"Reputation for {self.user.username}"

class UserRating(models.Model):
    RATING_TYPE_CHOICES = [
        ('seller', 'Vendeur'),
        ('buyer', 'Acheteur'),
    ]

    OUTCOME_CHOICES = [
        ('success', 'Réussi'),
        ('failed', 'Échoué'),
        ('disputed', 'Litigieux'),
        ('fraudulent', 'Frauduleux'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings')
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='ratings')
    rating_type = models.CharField(max_length=10, choices=RATING_TYPE_CHOICES)
    outcome = models.CharField(max_length=15, choices=OUTCOME_CHOICES)
    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'transaction', 'rating_type']

    def __str__(self):
        return f"{self.user.username} - {self.rating_type} - {self.outcome}"

# Modèles de chat et notifications (existants)
class Chat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='chat')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat for transaction {self.transaction.id}"

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message from {self.sender.username} at {self.created_at}"

class Notification(models.Model):
    TYPE_CHOICES = [
        ('purchase_intent', "Intention d'achat"),
        ('new_message', 'Nouveau message'),
        ('transaction_update', 'Mise à jour de transaction'),
        ('system', 'Notification système'),
        ('private_message', 'Message privé'),
        ('group_message', 'Message de groupe'),
        ('group_invite', 'Invitation de groupe'),
        ('friend_request', "Demande d'ami"),
        ('friend_accept', 'Amitié acceptée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    # Relations optionnelles
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"

# Modèles pour les informations de paiement vendeur
class SellerPaymentInfo(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('mobile_money', 'Mobile Money'),
        ('bank_transfer', 'Virement Bancaire'),
        ('card', 'Carte Bancaire'),
    ]

    OPERATOR_CHOICES = [
        ('orange_money', 'Orange Money'),
        ('mtn_momo', 'MTN Mobile Money'),
        ('moov_money', 'Moov Money'),
        ('wave', 'Wave'),
        ('free_money', 'Free Money'),
        ('emoney', 'E-Money'),
        ('airtel_money', 'Airtel Money'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='payment_info')
    
    # Méthode de paiement préférée
    preferred_payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='mobile_money')
    
    # Informations Mobile Money
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    operator = models.CharField(max_length=20, choices=OPERATOR_CHOICES, null=True, blank=True)
    country = models.CharField(max_length=2, default='SN')
    
    # Informations bancaires
    bank_name = models.CharField(max_length=100, null=True, blank=True)
    account_number = models.CharField(max_length=50, null=True, blank=True)
    account_holder_name = models.CharField(max_length=100, null=True, blank=True)
    swift_code = models.CharField(max_length=20, null=True, blank=True)
    iban = models.CharField(max_length=50, null=True, blank=True)
    
    # Informations carte
    card_number = models.CharField(max_length=20, null=True, blank=True)
    card_holder_name = models.CharField(max_length=100, null=True, blank=True)
    
    # Vérification
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment info for {self.user.username}"

# Modèles pour les groupes et messages privés
class Group(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    avatar = models.ImageField(upload_to='group_avatars/', null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_groups')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    max_members = models.IntegerField(default=100)

    class Meta:
        ordering = ['-last_message_at']

    def __str__(self):
        return self.name

class GroupMembership(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='group_memberships')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    is_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='added_members')

    class Meta:
        unique_together = ['user', 'group']
        ordering = ['joined_at']

    def __str__(self):
        return f"{self.user.username} in {self.group.name}"

class GroupMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_group_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Group message from {self.sender.username} in {self.group.name}"

class GroupMessageRead(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(GroupMessage, on_delete=models.CASCADE, related_name='read_by')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='read_group_messages')
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['message', 'user']

class PrivateConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_chats_as_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_chats_as_user2')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['user1', 'user2']
        ordering = ['-last_message_at']

    def __str__(self):
        return f"Conversation between {self.user1.username} and {self.user2.username}"

class PrivateMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    conversation = models.ForeignKey(PrivateConversation, on_delete=models.CASCADE, related_name='private_messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_private_messages')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Private message from {self.sender.username}"

# Modèles d'amitié
class FriendRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('accepted', 'Acceptée'),
        ('declined', 'Refusée'),
        ('cancelled', 'Annulée'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_requests_sent')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friend_requests_received')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['from_user', 'to_user']
        ordering = ['-created_at']

    def __str__(self):
        return f"Friend request from {self.from_user.username} to {self.to_user.username}"

class Friendship(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_as_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='friendships_as_user2')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user1', 'user2']
        constraints = [
            models.CheckConstraint(
                check=~models.Q(user1=models.F('user2')),
                name='no_self_friendship'
            )
        ]

    def __str__(self):
        return f"Friendship between {self.user1.username} and {self.user2.username}"

# Modèles d'escrow et payout (existants)
class EscrowTransaction(models.Model):
    STATUS_CHOICES = [
        ('in_escrow', 'En séquestre'),
        ('released', 'Libéré'),
        ('refunded', 'Remboursé'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    cinetpay_transaction = models.OneToOneField(CinetPayTransaction, on_delete=models.CASCADE, related_name='escrow')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_escrow')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='XOF')
    created_at = models.DateTimeField(auto_now_add=True)
    released_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Escrow {self.id} - {self.status}"

class PayoutRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Terminé'),
        ('failed', 'Échoué'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    escrow_transaction = models.ForeignKey(EscrowTransaction, on_delete=models.CASCADE, related_name='payout_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='XOF')
    recipient_phone = models.CharField(max_length=20)
    recipient_country = models.CharField(max_length=2)
    recipient_operator = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    cinetpay_payout_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Payout {self.id} - {self.status}"