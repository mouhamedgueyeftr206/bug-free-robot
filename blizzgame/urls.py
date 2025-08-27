from django.urls import path
from . import views
from . import webhook_handlers

urlpatterns = [
    # URLs existantes pour les comptes gaming
    path('', views.index, name='index'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('settings/', views.settings, name='settings'),
    path('create/', views.create, name='create'),
    path('product/<uuid:post_id>/', views.product_detail, name='product_detail'),
    path('delete/<uuid:post_id>/', views.delete_post, name='delete_post'),
    path('logout/', views.logout_view, name='logout'),
    
    # Authentification
    path('signin/', views.signin, name='signin'),
    path('signup/', views.signup, name='signup'),
    
    # Transactions gaming
    path('initiate-transaction/<uuid:post_id>/', views.initiate_transaction, name='initiate_transaction'),
    path('transaction/<uuid:transaction_id>/', views.transaction_detail, name='transaction_detail'),
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('confirm-reception/<uuid:transaction_id>/', views.confirm_reception, name='confirm_reception'),
    
    # CinetPay pour les comptes gaming
    path('payment/cinetpay/<uuid:transaction_id>/', views.initiate_cinetpay_payment, name='initiate_cinetpay_payment'),
    path('payment/cinetpay/notification/', views.cinetpay_notification, name='cinetpay_notification'),
    path('payment/cinetpay/success/<uuid:transaction_id>/', views.cinetpay_payment_success, name='cinetpay_payment_success'),
    path('payment/cinetpay/failed/<uuid:transaction_id>/', views.cinetpay_payment_failed, name='cinetpay_payment_failed'),
    
    # Informations de paiement vendeur
    path('seller/payment-setup/', views.seller_payment_setup, name='seller_payment_setup'),
    path('seller/payment-reset/', views.reset_payment_info, name='reset_payment_info'),
    
    # Chat et notifications
    path('chat/', views.chat_home, name='chat_home'),
    path('chat/list/', views.chat_list, name='chat_list'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-read/<uuid:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    
    # Chat privé et groupes
    path('chat/search/', views.user_search, name='user_search'),
    path('chat/private/<int:user_id>/', views.private_chat, name='private_chat'),
    path('chat/private/<uuid:conversation_id>/send/', views.send_private_message, name='send_private_message'),
    path('chat/private/<uuid:conversation_id>/messages/', views.get_private_messages, name='get_private_messages'),
    
    # Groupes
    path('chat/groups/', views.group_list, name='group_list'),
    path('chat/group/create/', views.create_group, name='create_group'),
    path('chat/group/<uuid:group_id>/', views.group_chat, name='group_chat'),
    path('chat/group/<uuid:group_id>/send/', views.send_group_message, name='send_group_message'),
    path('chat/group/<uuid:group_id>/messages/', views.get_group_messages, name='get_group_messages'),
    path('chat/group/<uuid:group_id>/members/', views.group_members, name='group_members'),
    path('chat/group/<uuid:group_id>/settings/', views.group_settings, name='group_settings'),
    path('chat/group/<uuid:group_id>/add-member/', views.add_group_member, name='add_group_member'),
    path('chat/group/<uuid:group_id>/remove-member/', views.remove_group_member, name='remove_group_member'),
    path('chat/group/<uuid:group_id>/promote/', views.promote_member, name='promote_member'),
    path('chat/group/<uuid:group_id>/leave/', views.leave_group, name='leave_group'),
    
    # Amis
    path('friends/', views.friend_requests, name='friend_requests'),
    path('friends/request/<int:user_id>/', views.send_friend_request, name='send_friend_request'),
    path('friends/accept/<uuid:request_id>/', views.accept_friend_request, name='accept_friend_request'),
    path('friends/decline/<uuid:request_id>/', views.decline_friend_request, name='decline_friend_request'),
    path('friends/cancel/<uuid:request_id>/', views.cancel_friend_request, name='cancel_friend_request'),
    
    # === NOUVELLES URLs BOUTIQUE E-COMMERCE ===
    
    # Pages principales boutique
    path('shop/', views.shop_home, name='shop_home'),
    path('shop/products/', views.shop_products, name='shop_products'),
    path('shop/product/<slug:slug>/', views.shop_product_detail, name='shop_product_detail'),
    path('shop/category/<slug:slug>/', views.shop_category, name='shop_category'),
    
    # Gestion du panier
    path('shop/cart/', views.cart_view, name='cart_view'),
    path('shop/cart/add/', views.add_to_cart, name='add_to_cart'),
    path('shop/cart/update/', views.update_cart_item, name='update_cart_item'),
    path('shop/cart/remove/', views.remove_from_cart, name='remove_from_cart'),
    
    # Processus de commande
    path('shop/checkout/', views.checkout, name='checkout'),
    path('shop/payment/<uuid:order_id>/', views.shop_payment, name='shop_payment'),
    
    # CinetPay pour la boutique
    path('shop/payment/cinetpay/initiate/<uuid:order_id>/', views.shop_payment, name='initiate_shop_payment'),
    path('shop/payment/cinetpay/notification/', views.shop_cinetpay_notification, name='shop_cinetpay_notification'),
    path('shop/payment/cinetpay/success/<uuid:order_id>/', views.shop_payment_success, name='shop_payment_success'),
    path('shop/payment/cinetpay/failed/<uuid:order_id>/', views.shop_payment_failed, name='shop_payment_failed'),
    
    # Commandes utilisateur
    path('shop/orders/', views.my_orders, name='my_orders'),
    path('shop/order/<uuid:order_id>/', views.order_detail, name='order_detail'),
    
    # Administration
    path('admin/sync-shopify/', views.sync_shopify_products, name='sync_shopify_products'),
    
    # Webhooks Shopify
    path('webhooks/shopify/orders/', webhook_handlers.shopify_order_webhook, name='shopify_order_webhook'),
    path('webhooks/shopify/fulfillments/', webhook_handlers.shopify_fulfillment_webhook, name='shopify_fulfillment_webhook'),
    path('webhooks/shopify/refunds/', webhook_handlers.shopify_refund_webhook, name='shopify_refund_webhook'),
    path('webhooks/shopify/products/create/', webhook_handlers.shopify_product_create_webhook, name='shopify_product_create_webhook'),
    path('webhooks/shopify/products/update/', webhook_handlers.shopify_product_update_webhook, name='shopify_product_update_webhook'),
    path('webhooks/shopify/products/delete/', webhook_handlers.shopify_product_delete_webhook, name='shopify_product_delete_webhook'),
    
    # === URLs HIGHLIGHTS ===
    
    # Pages principales Highlights
    path('highlights/', views.highlights_home, name='highlights_home'),
    path('highlights/for-you/', views.highlights_for_you, name='highlights_for_you'),
    path('highlights/friends/', views.highlights_friends, name='highlights_friends'),
    path('highlights/search/', views.highlights_search, name='highlights_search'),
    path('highlights/hashtag/<str:hashtag>/', views.highlights_hashtag, name='highlights_hashtag'),
    
    # Gestion des Highlights
    path('highlights/create/', views.create_highlight, name='create_highlight'),
    path('highlights/<uuid:highlight_id>/', views.highlight_detail, name='highlight_detail'),
    path('highlights/<uuid:highlight_id>/delete/', views.delete_highlight, name='delete_highlight'),
    
    # Actions sur les Highlights
    path('highlights/<uuid:highlight_id>/appreciate/', views.toggle_highlight_appreciation, name='toggle_highlight_appreciation'),
    path('highlights/<uuid:highlight_id>/comment/', views.add_highlight_comment, name='add_highlight_comment'),
    path('highlights/<uuid:highlight_id>/share/', views.share_highlight, name='share_highlight'),
    path('highlights/<uuid:highlight_id>/view/', views.record_highlight_view, name='record_highlight_view'),
    path('highlights/<uuid:highlight_id>/view-enhanced/', views.record_highlight_view_enhanced, name='record_highlight_view_enhanced'),
    
    # Système d'abonnement
    path('subscribe/<int:user_id>/', views.toggle_subscription, name='toggle_subscription'),
    path('subscriptions/', views.my_subscriptions, name='my_subscriptions'),
    path('subscribers/', views.my_subscribers, name='my_subscribers'),
    
    # API pour les Highlights (AJAX)
    path('api/highlights/feed/', views.highlights_feed_api, name='highlights_feed_api'),
    path('api/highlights/<uuid:highlight_id>/comments/', views.highlight_comments_api, name='highlight_comments_api'),
]