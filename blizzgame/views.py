from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, Sum
from django.utils import timezone
from django.conf import settings
from django.db import models
import json
import logging

from .models import (
    Profile, Post, PostImage, PostVideo, Transaction, Notification,
    Product, ProductCategory, Cart, CartItem, Order, OrderItem, ShopCinetPayTransaction,
    ProductVariant, UserReputation, SellerPaymentInfo, Highlight, HighlightAppreciation, 
    HighlightComment, HighlightView, HighlightShare, UserSubscription, FriendRequest, Friendship,
    PrivateConversation, PrivateMessage, Group, GroupMembership, GroupMessage, GroupMessageRead
)
from .shopify_utils import create_shopify_order_from_blizz_order, sync_products_from_shopify
from .cinetpay_utils import CinetPayAPI, handle_cinetpay_notification, convert_currency_for_cinetpay
from django.db.models import Exists, OuterRef
import re

logger = logging.getLogger(__name__)

# ===== Vues existantes simples (stubs pour garantir l'import) =====

def index(request):
	posts = Post.objects.all().order_by('-created_at')[:20]
	return render(request, 'index.html', {'posts': posts})

def profile(request, username):
    user = get_object_or_404(User, username=username)
    prof = getattr(user, 'profile', None)
    user_posts = Post.objects.filter(author=user).order_by('-created_at')
    
    # Calculer les statistiques pour la page profile
    total_sales = Post.objects.filter(author=user, is_sold=True).count()
    
    context = {
        'profile': prof,
        'user_obj': user,
        'user_profile': prof,  # Pour compatibilité avec le template
        'posts': user_posts,
        'total_sales': total_sales,
        'rating': 0,  # Initialisé à zéro
    }
    return render(request, 'profile.html', context)

@login_required
def settings(request):
    if request.method == 'POST':
        prof = request.user.profile
        prof.bio = request.POST.get('bio', prof.bio)
        prof.location = request.POST.get('location', prof.location)
        
        # Gestion des images
        if 'profileimg' in request.FILES:
            prof.profileimg = request.FILES['profileimg']
        if 'banner' in request.FILES:
            prof.banner = request.FILES['banner']
        
        # Gestion des jeux favoris
        favorite_games = request.POST.getlist('favorite_games')
        prof.favorite_games = favorite_games
        
        prof.save()
        messages.success(request, 'Profil mis à jour')
        return redirect('settings')
    
    # Préparer les données pour le template
    from blizzgame.models import Profile
    game_choices = Profile.GAME_CHOICES
    user_favorite_games = request.user.profile.favorite_games if hasattr(request.user, 'profile') else []
    
    context = {
        'game_choices': game_choices,
        'user_favorite_games': user_favorite_games,
        'user_profile': request.user.profile,
    }
    return render(request, 'settings.html', context)

@login_required
def create(request):
    if request.method == 'POST':
        title = request.POST.get('title', 'sans nom')
        caption = request.POST.get('caption', '')
        price = request.POST.get('price', '0')
        post = Post.objects.create(user=request.user.username, author=request.user, title=title, caption=caption, price=price)
        return redirect('product_detail', post_id=post.id)
    return render(request, 'create.html')

def product_detail(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    return render(request, 'product_detail.html', {'post': post})

@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    post.delete()
    return redirect('index')

def logout_view(request):
    logout(request)
    return redirect('index')

def signin(request):
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        if username and password:
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'Bienvenue {username}!')
                return redirect('index')
            else:
                messages.error(request, 'Nom d\'utilisateur ou mot de passe incorrect.')
        else:
            messages.error(request, 'Veuillez remplir tous les champs.')
    
    return render(request, 'signin.html')

def signup(request):
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        terms = request.POST.get('terms')
        
        if not all([username, email, password, password2, terms]):
            messages.error(request, 'Veuillez remplir tous les champs et accepter les conditions.')
            return render(request, 'signup.html')
        
        if password != password2:
            messages.error(request, 'Les mots de passe ne correspondent pas.')
            return render(request, 'signup.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Ce nom d\'utilisateur existe déjà.')
            return render(request, 'signup.html')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Cet email est déjà utilisé.')
            return render(request, 'signup.html')
        
        try:
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )
            
            # Créer le profil utilisateur
            Profile.objects.create(user=user, id_user=user.id)
            
            # Ré-authentifier pour attacher le backend avant la connexion
            user = authenticate(request, username=username, password=password)
            if user is None:
                messages.error(request, "Impossible d'authentifier le nouvel utilisateur. Réessayez.")
                return render(request, 'signup.html')
            
            # Connecter l'utilisateur
            login(request, user)
            messages.success(request, f'Compte créé avec succès! Bienvenue {username}!')
            return redirect('index')
            
        except Exception as e:
            messages.error(request, f'Erreur lors de la création du compte: {str(e)}')
    
    return render(request, 'signup.html')

# ===== Transactions gaming (stubs minimaux) =====

@login_required
def initiate_transaction(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    transaction = Transaction.objects.create(buyer=request.user, seller=post.author, post=post, amount=post.price)
    return redirect('transaction_detail', transaction_id=transaction.id)

@login_required
def transaction_detail(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    return render(request, 'cinetpay_payment_form.html', {'transaction': transaction})

@login_required
def transaction_list(request):
    txs = Transaction.objects.filter(Q(buyer=request.user) | Q(seller=request.user)).order_by('-created_at')
    return render(request, 'notifications.html', {'transactions': txs})

@login_required
def confirm_reception(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id, buyer=request.user)
    transaction.status = 'completed'
    transaction.completed_at = timezone.now()
    transaction.save()
    messages.success(request, 'Réception confirmée')
    return redirect('transaction_detail', transaction_id=transaction.id)

# ===== CinetPay pour transactions gaming existantes (stubs) =====

@login_required
def initiate_cinetpay_payment(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    return render(request, 'cinetpay_payment_form.html', {'transaction': transaction})

@csrf_exempt
def cinetpay_notification(request):
    return HttpResponse('OK', status=200)

def cinetpay_payment_success(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    transaction.status = 'completed'
    transaction.save()
    return render(request, 'cinetpay_success.html', {'transaction': transaction})

def cinetpay_payment_failed(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    transaction.status = 'failed'
    transaction.save()
    return render(request, 'cinetpay_failed.html', {'transaction': transaction})

# ===== Chat, notifications et amis (stubs basiques pour éviter les erreurs d'import) =====

def chat_home(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Récupérer les conversations privées de l'utilisateur
    private_conversations = PrivateConversation.objects.filter(
        models.Q(user1=request.user) | models.Q(user2=request.user),
        is_active=True
    ).select_related('user1', 'user2').order_by('-last_message_at')[:10]
    
    # Préparer les données des conversations
    conversations_data = []
    for conv in private_conversations:
        other_user = conv.user2 if conv.user1 == request.user else conv.user1
        last_message = conv.private_messages.order_by('-created_at').first()
        
        conversations_data.append({
            'conversation': conv,
            'other_user': other_user,
            'last_message': last_message,
            'unread_count': conv.private_messages.filter(
                is_read=False
            ).exclude(sender=request.user).count()
        })
    
    # Récupérer les groupes de l'utilisateur
    user_groups = Group.objects.filter(
        memberships__user=request.user,
        memberships__is_active=True,
        is_active=True
    ).select_related('created_by').order_by('-last_message_at')[:5]
    
    context = {
        'conversations': conversations_data,
        'groups': user_groups,
    }
    
    return render(request, 'chat/chat_home.html', context)

def chat_list(request):
    return render(request, 'chat_list.html')

def notifications(request):
    notes = Notification.objects.filter(user=request.user) if request.user.is_authenticated else []
    return render(request, 'notifications.html', {'notifications': notes})

def mark_notification_read(request, notification_id):
    note = get_object_or_404(Notification, id=notification_id, user=request.user)
    note.is_read = True
    note.save()
    return redirect('notifications')

def user_search(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    user_profile = getattr(request.user, 'profile', None)
    user_favorite_games = user_profile.favorite_games if user_profile else []
    
    user_friendships = Friendship.objects.filter(
        models.Q(user1=request.user) | models.Q(user2=request.user)
    )
    
    existing_friends = set()
    for friendship in user_friendships:
        if friendship.user1 == request.user:
            existing_friends.add(friendship.user2.id)
        else:
            existing_friends.add(friendship.user1.id)
    
    existing_requests = set(
        FriendRequest.objects.filter(
            models.Q(from_user=request.user) | models.Q(to_user=request.user),
            status='pending'
        ).values_list('from_user_id', 'to_user_id')
    )
    
    blocked_users = set()
    for from_id, to_id in existing_requests:
        if from_id == request.user.id:
            blocked_users.add(to_id)
        else:
            blocked_users.add(from_id)
    
    excluded_users = existing_friends | blocked_users | {request.user.id}
    search_query = request.GET.get('q', '').strip()
    
    if search_query:
        # Recherche simple par nom d'utilisateur sans limitation par jeux favoris
        search_results = User.objects.filter(
            username__icontains=search_query
        ).exclude(id__in=excluded_users).select_related('profile')[:50]
        
        recommendations = []
        for user in search_results:
            user_games = user.profile.favorite_games if user.profile else []
            common_games = set(user_favorite_games) & set(user_games) if user_favorite_games else set()
            similarity_score = len(common_games)
            recommendations.append((user, similarity_score, list(common_games)))
    else:
        recommendations = []
        if user_favorite_games:
            potential_users = User.objects.filter(
                profile__favorite_games__overlap=user_favorite_games
            ).exclude(id__in=excluded_users).select_related('profile')[:20]
            
            user_scores = []
            for user in potential_users:
                user_games = user.profile.favorite_games if user.profile else []
                common_games = set(user_favorite_games) & set(user_games)
                similarity_score = len(common_games)
                if similarity_score > 0:
                    user_scores.append((user, similarity_score, list(common_games)))
            
            user_scores.sort(key=lambda x: x[1], reverse=True)
            recommendations = user_scores[:10]
        
        if len(recommendations) < 10:
            remaining_slots = 10 - len(recommendations)
            recommended_user_ids = {user[0].id for user in recommendations}
            
            random_users = User.objects.exclude(
                id__in=excluded_users | recommended_user_ids
            ).select_related('profile').order_by('?')[:remaining_slots]
            
            for user in random_users:
                user_games = user.profile.favorite_games if user.profile else []
                common_games = set(user_favorite_games) & set(user_games) if user_favorite_games else set()
                recommendations.append((user, len(common_games), list(common_games)))
    
    context = {
        'recommendations': recommendations,
        'user_favorite_games': user_favorite_games,
        'search_query': search_query,
    }
    
    return render(request, 'chat/user_search.html', context)

def private_chat(request, user_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    other = get_object_or_404(User, id=user_id)
    
    # Vérifier qu'on ne peut pas chatter avec soi-même
    if other == request.user:
        messages.error(request, "Vous ne pouvez pas chatter avec vous-même.")
        return redirect('chat_home')
    
    # Créer ou récupérer la conversation privée
    conversation = PrivateConversation.objects.filter(
        models.Q(user1=request.user, user2=other) |
        models.Q(user1=other, user2=request.user)
    ).first()
    
    if not conversation:
        # Créer une nouvelle conversation
        conversation = PrivateConversation.objects.create(
            user1=request.user,
            user2=other
        )
    
    # Récupérer les derniers messages (50 max)
    messages_list = conversation.private_messages.select_related('sender').order_by('-created_at')[:50]
    messages_list = list(reversed(messages_list))  # Ordre chronologique
    
    # Marquer les messages comme lus
    unread_messages = conversation.private_messages.filter(
        is_read=False
    ).exclude(sender=request.user)
    
    for message in unread_messages:
        message.is_read = True
        message.read_at = timezone.now()
    
    PrivateMessage.objects.bulk_update(unread_messages, ['is_read', 'read_at'])
    
    context = {
        'other': other,
        'conversation': conversation,
        'messages': messages_list,
    }
    
    return render(request, 'chat/private_chat.html', context)

@require_POST
def send_private_message(request, conversation_id):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Non authentifié'})
    
    try:
        conversation = get_object_or_404(PrivateConversation, id=conversation_id)
        
        # Vérifier que l'utilisateur fait partie de la conversation
        if request.user not in [conversation.user1, conversation.user2]:
            return JsonResponse({'success': False, 'error': 'Accès non autorisé'})
        
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({'success': False, 'error': 'Message vide'})
        
        if len(content) > 1000:
            return JsonResponse({'success': False, 'error': 'Message trop long (max 1000 caractères)'})
        
        # Créer le message
        message = PrivateMessage.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content
        )
        
        # Mettre à jour le timestamp de la conversation
        conversation.last_message_at = timezone.now()
        conversation.save()
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': str(message.id),
                'content': message.content,
                'sender': message.sender.username,
                'created_at': message.created_at.isoformat(),
                'is_own': message.sender == request.user
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur envoi message privé: {e}")
        return JsonResponse({'success': False, 'error': 'Erreur serveur'})

def get_private_messages(request, conversation_id):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Non authentifié'})
    
    try:
        conversation = get_object_or_404(PrivateConversation, id=conversation_id)
        
        # Vérifier que l'utilisateur fait partie de la conversation
        if request.user not in [conversation.user1, conversation.user2]:
            return JsonResponse({'success': False, 'error': 'Accès non autorisé'})
        
        # Paramètres de pagination
        page = int(request.GET.get('page', 1))
        limit = min(int(request.GET.get('limit', 20)), 50)  # Max 50 messages
        offset = (page - 1) * limit
        
        # Récupérer les messages
        messages_query = conversation.private_messages.select_related('sender').order_by('-created_at')
        total_messages = messages_query.count()
        messages_list = messages_query[offset:offset + limit]
        
        messages_data = []
        for message in reversed(messages_list):  # Ordre chronologique
            messages_data.append({
                'id': str(message.id),
                'content': message.content,
                'sender': message.sender.username,
                'sender_id': message.sender.id,
                'created_at': message.created_at.isoformat(),
                'is_read': message.is_read,
                'is_own': message.sender == request.user,
                'is_edited': message.is_edited
            })
        
        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_messages,
                'has_more': offset + limit < total_messages
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur récupération messages: {e}")
        return JsonResponse({'success': False, 'error': 'Erreur serveur'})

def group_list(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Récupérer les groupes dont l'utilisateur est membre
    user_groups = Group.objects.filter(
        memberships__user=request.user,
        memberships__is_active=True,
        is_active=True
    ).select_related('created_by').prefetch_related('memberships').order_by('-last_message_at')
    
    # Ajouter des informations supplémentaires pour chaque groupe
    groups_data = []
    for group in user_groups:
        membership = group.memberships.filter(user=request.user, is_active=True).first()
        groups_data.append({
            'group': group,
            'is_admin': membership.is_admin if membership else False,
            'member_count': group.memberships.filter(is_active=True).count(),
            'unread_count': 0  # TODO: Implémenter le comptage des messages non lus
        })
    
    context = {
        'groups_data': groups_data,
    }
    
    return render(request, 'chat/group_list.html', context)

@login_required
def create_group(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not name:
            messages.error(request, "Le nom du groupe est requis.")
            return render(request, 'chat/create_group.html')
        
        if len(name) > 100:
            messages.error(request, "Le nom du groupe est trop long (max 100 caractères).")
            return render(request, 'chat/create_group.html')
        
        try:
            # Créer le groupe
            group = Group.objects.create(
                name=name,
                description=description,
                created_by=request.user
            )
            
            # Ajouter le créateur comme membre admin
            GroupMembership.objects.create(
                user=request.user,
                group=group,
                is_admin=True,
                added_by=request.user
            )
            
            messages.success(request, f"Groupe '{name}' créé avec succès.")
            return redirect('group_chat', group_id=group.id)
            
        except Exception as e:
            logger.error(f"Erreur création groupe: {e}")
            messages.error(request, "Erreur lors de la création du groupe.")
    
    return render(request, 'chat/create_group.html')

def group_chat(request, group_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        group = get_object_or_404(Group, id=group_id, is_active=True)
        
        # Vérifier que l'utilisateur est membre du groupe
        membership = GroupMembership.objects.filter(
            user=request.user,
            group=group,
            is_active=True
        ).first()
        
        if not membership:
            messages.error(request, "Vous n'êtes pas membre de ce groupe.")
            return redirect('group_list')
        
        # Récupérer les derniers messages (50 max)
        messages_list = group.group_messages.select_related('sender').order_by('-created_at')[:50]
        messages_list = list(reversed(messages_list))  # Ordre chronologique
        
        # Récupérer les membres du groupe
        members = GroupMembership.objects.filter(
            group=group,
            is_active=True
        ).select_related('user').order_by('-is_admin', 'joined_at')
        
        context = {
            'group': group,
            'membership': membership,
            'messages': messages_list,
            'members': members,
            'member_count': members.count(),
        }
        
        return render(request, 'chat/group_chat.html', context)
        
    except Exception as e:
        logger.error(f"Erreur accès groupe: {e}")
        messages.error(request, "Erreur lors de l'accès au groupe.")
        return redirect('group_list')

@require_POST
def send_group_message(request, group_id):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Non authentifié'})
    
    try:
        group = get_object_or_404(Group, id=group_id, is_active=True)
        
        # Vérifier que l'utilisateur est membre du groupe
        membership = GroupMembership.objects.filter(
            user=request.user,
            group=group,
            is_active=True
        ).first()
        
        if not membership:
            return JsonResponse({'success': False, 'error': 'Vous n\'\u00eates pas membre de ce groupe'})
        
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({'success': False, 'error': 'Message vide'})
        
        if len(content) > 1000:
            return JsonResponse({'success': False, 'error': 'Message trop long (max 1000 caractères)'})
        
        # Créer le message
        message = GroupMessage.objects.create(
            group=group,
            sender=request.user,
            content=content
        )
        
        # Mettre à jour le timestamp du groupe
        group.last_message_at = timezone.now()
        group.save()
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': str(message.id),
                'content': message.content,
                'sender': message.sender.username,
                'created_at': message.created_at.isoformat(),
                'is_own': message.sender == request.user
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur envoi message groupe: {e}")
        return JsonResponse({'success': False, 'error': 'Erreur serveur'})

def get_group_messages(request, group_id):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Non authentifié'})
    
    try:
        group = get_object_or_404(Group, id=group_id, is_active=True)
        
        # Vérifier que l'utilisateur est membre du groupe
        membership = GroupMembership.objects.filter(
            user=request.user,
            group=group,
            is_active=True
        ).first()
        
        if not membership:
            return JsonResponse({'success': False, 'error': 'Accès non autorisé'})
        
        # Paramètres de pagination
        page = int(request.GET.get('page', 1))
        limit = min(int(request.GET.get('limit', 20)), 50)  # Max 50 messages
        offset = (page - 1) * limit
        
        # Récupérer les messages
        messages_query = group.group_messages.select_related('sender').order_by('-created_at')
        total_messages = messages_query.count()
        messages_list = messages_query[offset:offset + limit]
        
        messages_data = []
        for message in reversed(messages_list):  # Ordre chronologique
            messages_data.append({
                'id': str(message.id),
                'content': message.content,
                'sender': message.sender.username,
                'sender_id': message.sender.id,
                'created_at': message.created_at.isoformat(),
                'is_own': message.sender == request.user,
                'is_edited': message.is_edited
            })
        
        return JsonResponse({
            'success': True,
            'messages': messages_data,
            'pagination': {
                'page': page,
                'limit': limit,
                'total': total_messages,
                'has_more': offset + limit < total_messages
            }
        })
        
    except Exception as e:
        logger.error(f"Erreur récupération messages groupe: {e}")
        return JsonResponse({'success': False, 'error': 'Erreur serveur'})

def group_members(request, group_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        group = get_object_or_404(Group, id=group_id, is_active=True)
        
        # Vérifier que l'utilisateur est membre du groupe
        user_membership = GroupMembership.objects.filter(
            user=request.user,
            group=group,
            is_active=True
        ).first()
        
        if not user_membership:
            messages.error(request, "Vous n'êtes pas membre de ce groupe.")
            return redirect('group_list')
        
        # Récupérer tous les membres
        members = GroupMembership.objects.filter(
            group=group,
            is_active=True
        ).select_related('user', 'added_by').order_by('-is_admin', 'joined_at')
        
        context = {
            'group': group,
            'members': members,
            'user_membership': user_membership,
            'can_manage': user_membership.is_admin or group.created_by == request.user,
        }
        
        return render(request, 'chat/group_members.html', context)
        
    except Exception as e:
        logger.error(f"Erreur accès membres groupe: {e}")
        messages.error(request, "Erreur lors de l'accès aux membres du groupe.")
        return redirect('group_list')

def group_settings(request, group_id):
    return render(request, 'chat/group_settings.html')

def add_group_member(request, group_id):
    return JsonResponse({'success': True})

def remove_group_member(request, group_id):
    return JsonResponse({'success': True})

def promote_member(request, group_id):
    return JsonResponse({'success': True})

def leave_group(request, group_id):
    return JsonResponse({'success': True})

def friend_requests(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # Récupérer les demandes d'ami reçues (en attente)
    pending_received = FriendRequest.objects.filter(
        to_user=request.user, 
        status='pending'
    ).select_related('from_user')
    
    # Récupérer les demandes d'ami envoyées (en attente)
    pending_sent = FriendRequest.objects.filter(
        from_user=request.user, 
        status='pending'
    ).select_related('to_user')
    
    # Récupérer les amis existants (friendships bidirectionnelles)
    user_friendships = Friendship.objects.filter(
        models.Q(user1=request.user) | models.Q(user2=request.user)
    )
    
    friends = []
    for friendship in user_friendships:
        if friendship.user1 == request.user:
            friends.append(friendship.user2)
        else:
            friends.append(friendship.user1)
    
    context = {
        'friends': friends,
        'pending_received': pending_received,
        'pending_sent': pending_sent,
    }
    
    return render(request, 'chat/friends.html', context)

def send_friend_request(request, user_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        to_user = User.objects.get(id=user_id)
        
        # Vérifier qu'on n'envoie pas une demande à soi-même
        if to_user == request.user:
            messages.error(request, "Vous ne pouvez pas vous envoyer une demande d'ami.")
            return redirect('user_search')
        
        # Vérifier si une demande existe déjà
        existing_request = FriendRequest.objects.filter(
            models.Q(from_user=request.user, to_user=to_user) |
            models.Q(from_user=to_user, to_user=request.user),
            status='pending'
        ).first()
        
        if existing_request:
            messages.warning(request, "Une demande d'ami est déjà en cours avec cet utilisateur.")
            return redirect('user_search')
        
        # Vérifier si ils sont déjà amis
        existing_friendship = Friendship.objects.filter(
            models.Q(user1=request.user, user2=to_user) |
            models.Q(user1=to_user, user2=request.user)
        ).first()
        
        if existing_friendship:
            messages.info(request, "Vous êtes déjà amis avec cet utilisateur.")
            return redirect('user_search')
        
        # Créer la demande d'ami
        FriendRequest.objects.create(
            from_user=request.user,
            to_user=to_user,
            status='pending'
        )
        
        messages.success(request, f"Demande d'ami envoyée à {to_user.username}.")
        
    except User.DoesNotExist:
        messages.error(request, "Utilisateur introuvable.")
    
    return redirect('user_search')

def accept_friend_request(request, request_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        friend_request = FriendRequest.objects.get(
            id=request_id,
            to_user=request.user,
            status='pending'
        )
        
        # Marquer la demande comme acceptée
        friend_request.status = 'accepted'
        friend_request.responded_at = timezone.now()
        friend_request.save()
        
        # Créer l'amitié bidirectionnelle
        Friendship.objects.create(
            user1=friend_request.from_user,
            user2=friend_request.to_user
        )
        
        messages.success(request, f"Vous êtes maintenant ami avec {friend_request.from_user.username}.")
        
    except FriendRequest.DoesNotExist:
        messages.error(request, "Demande d'ami introuvable.")
    
    return redirect('friend_requests')

def decline_friend_request(request, request_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        friend_request = FriendRequest.objects.get(
            id=request_id,
            to_user=request.user,
            status='pending'
        )
        
        # Marquer la demande comme refusée
        friend_request.status = 'declined'
        friend_request.responded_at = timezone.now()
        friend_request.save()
        
        messages.info(request, f"Demande d'ami de {friend_request.from_user.username} refusée.")
        
    except FriendRequest.DoesNotExist:
        messages.error(request, "Demande d'ami introuvable.")
    
    return redirect('friend_requests')

def cancel_friend_request(request, request_id):
    if not request.user.is_authenticated:
        return redirect('login')
    
    try:
        friend_request = FriendRequest.objects.get(
            id=request_id,
            from_user=request.user,
            status='pending'
        )
        
        # Marquer la demande comme annulée
        friend_request.status = 'cancelled'
        friend_request.responded_at = timezone.now()
        friend_request.save()
        
        messages.info(request, f"Demande d'ami à {friend_request.to_user.username} annulée.")
        
    except FriendRequest.DoesNotExist:
        messages.error(request, "Demande d'ami introuvable.")
    
    return redirect('friend_requests')

# ===== Boutique E-commerce =====

def shop_home(request):
    try:
        categories = ProductCategory.objects.filter(is_active=True, parent=None)[:6]
        featured_products = Product.objects.filter(status='active', is_featured=True)[:8]
        new_products = Product.objects.filter(status='active').order_by('-created_at')[:8]
        context = {
            'categories': categories,
            'featured_products': featured_products,
            'new_products': new_products,
        }
        return render(request, 'shop/home.html', context)
    except Exception as e:
        logger.error(f"Erreur dans shop_home: {e}")
        messages.error(request, "Erreur lors du chargement de la boutique")
        return redirect('index')

def shop_products(request):
    try:
        products = Product.objects.filter(status='active')
        categories = ProductCategory.objects.filter(is_active=True)
        category_slug = request.GET.get('category')
        if category_slug:
            products = products.filter(category__slug=category_slug)
        min_price = request.GET.get('min_price')
        if min_price:
            products = products.filter(price__gte=min_price)
        max_price = request.GET.get('max_price')
        if max_price:
            products = products.filter(price__lte=max_price)
        sort = request.GET.get('sort', '-created_at')
        if sort in ['name', '-name', 'price', '-price', '-created_at', 'created_at']:
            products = products.order_by(sort)
        paginator = Paginator(products, 12)
        page_number = request.GET.get('page')
        products = paginator.get_page(page_number)
        context = {
            'products': products,
            'categories': categories,
            'current_sort': sort,
        }
        return render(request, 'shop/products.html', context)
    except Exception as e:
        logger.error(f"Erreur dans shop_products: {e}")
        messages.error(request, "Erreur lors du chargement des produits")
        return redirect('shop_home')

def shop_product_detail(request, slug):
    try:
        product = get_object_or_404(Product, slug=slug, status='active')
        # Récupérer toutes les images du produit pour le carrousel
        product_images = product.images.all().order_by('order')
        # Si pas d'images, utiliser l'image principale
        if not product_images.exists() and product.featured_image:
            product_images = [product.featured_image]
        related_products = Product.objects.filter(category=product.category, status='active').exclude(id=product.id)[:4]
        context = {
            'product': product,
            'product_images': product_images,
            'related_products': related_products,
        }
        return render(request, 'shop/product_detail.html', context)
    except Exception as e:
        logger.error(f"Erreur dans shop_product_detail: {e}")
        messages.error(request, "Produit non trouvé")
        return redirect('shop_products')

def shop_category(request, slug):
    try:
        category = get_object_or_404(ProductCategory, slug=slug, is_active=True)
        products = Product.objects.filter(category=category, status='active')
        min_price = request.GET.get('min_price')
        if min_price:
            products = products.filter(price__gte=min_price)
        max_price = request.GET.get('max_price')
        if max_price:
            products = products.filter(price__lte=max_price)
        sort = request.GET.get('sort', '-created_at')
        if sort in ['name', '-name', 'price', '-price', '-created_at']:
            products = products.order_by(sort)
        paginator = Paginator(products, 12)
        page_number = request.GET.get('page')
        products = paginator.get_page(page_number)
        context = {
            'category': category,
            'products': products,
            'current_sort': sort,
            'price_min': min_price,
            'price_max': max_price,
        }
        return render(request, 'shop/category.html', context)
    except Exception as e:
        logger.error(f"Erreur dans shop_category: {e}")
        messages.error(request, "Catégorie non trouvée")
        return redirect('shop_products')

# ===== Panier =====

def get_or_create_cart(request):
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
    else:
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        cart, _ = Cart.objects.get_or_create(session_key=session_key)
    return cart

@require_POST
def add_to_cart(request):
    try:
        product_id = request.POST.get('product_id')
        quantity = int(request.POST.get('quantity', 1))
        variant_id = request.POST.get('variant_id')
        if not product_id:
            return JsonResponse({'success': False, 'message': 'Produit non spécifié'})
        product = get_object_or_404(Product, id=product_id, status='active')
        variant = None
        if variant_id:
            variant = get_object_or_404(ProductVariant, id=variant_id, product=product)
            price = variant.get_final_price()
        else:
            price = product.price
        cart = get_or_create_cart(request)
        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            variant=variant,
            defaults={'quantity': quantity, 'price': price}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
        return JsonResponse({'success': True, 'message': 'Produit ajouté au panier', 'cart_count': cart.get_total_items()})
    except Exception as e:
        logger.error(f"Erreur add_to_cart: {e}")
        return JsonResponse({'success': False, 'message': "Erreur lors de l'ajout au panier"})

def cart_view(request):
    try:
        cart = get_or_create_cart(request)
        return render(request, 'shop/cart.html', {'cart': cart})
    except Exception as e:
        logger.error(f"Erreur cart_view: {e}")
        messages.error(request, "Erreur lors du chargement du panier")
        return redirect('shop_home')

@require_POST
def update_cart_item(request):
    try:
        item_id = request.POST.get('item_id')
        quantity = int(request.POST.get('quantity', 1))
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        if quantity > 0:
            cart_item.quantity = quantity
            cart_item.save()
        else:
            cart_item.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Erreur update_cart_item: {e}")
        return JsonResponse({'success': False, 'message': 'Erreur lors de la mise à jour'})

@require_POST
def remove_from_cart(request):
    try:
        item_id = request.POST.get('item_id')
        cart = get_or_create_cart(request)
        cart_item = get_object_or_404(CartItem, id=item_id, cart=cart)
        cart_item.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Erreur remove_from_cart: {e}")
        return JsonResponse({'success': False, 'message': 'Erreur lors de la suppression'})

# ===== Checkout et Paiement Boutique (CinetPay) =====

def checkout(request):
    try:
        cart = get_or_create_cart(request)
        if cart.is_empty:
            messages.warning(request, 'Votre panier est vide')
            return redirect('cart_view')
        if request.method == 'POST':
            try:
                order = Order.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    customer_email=request.POST.get('email'),
                    customer_phone=request.POST.get('phone'),
                    customer_first_name=request.POST.get('first_name'),
                    customer_last_name=request.POST.get('last_name'),
                    shipping_address_line1=request.POST.get('address_line1'),
                    shipping_address_line2=request.POST.get('address_line2', ''),
                    shipping_city=request.POST.get('city'),
                    shipping_state=request.POST.get('state'),
                    shipping_postal_code=request.POST.get('postal_code'),
                    shipping_country=request.POST.get('country'),
                    subtotal=cart.get_total_price(),
                    total_amount=cart.get_total_price(),
                )
                for cart_item in cart.items.all():
                    OrderItem.objects.create(
                        order=order,
                        product=cart_item.product,
                        variant=cart_item.variant,
                        product_name=cart_item.product.name,
                        product_price=cart_item.price,
                        quantity=cart_item.quantity,
                        total_price=cart_item.get_total_price()
                    )
                cart.items.all().delete()
                return redirect('shop_payment', order_id=order.id)
            except Exception as e:
                logger.error(f"Erreur lors de la création de commande: {e}")
                messages.error(request, 'Erreur lors de la création de la commande')
        return render(request, 'shop/checkout.html', {'cart': cart})
    except Exception as e:
        logger.error(f"Erreur checkout: {e}")
        messages.error(request, 'Erreur lors du processus de commande')
        return redirect('cart_view')

def shop_payment(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id)
        if order.user and request.user.is_authenticated and order.user != request.user:
            messages.error(request, 'Commande non autorisée')
            return redirect('shop_home')
        if request.method == 'POST':
            customer_data = {
                'customer_name': request.POST.get('customer_name'),
                'customer_surname': request.POST.get('customer_surname'),
                'customer_email': request.POST.get('customer_email'),
                'customer_phone_number': request.POST.get('customer_phone_number'),
                'customer_address': request.POST.get('customer_address'),
                'customer_city': request.POST.get('customer_city'),
                'customer_country': request.POST.get('customer_country'),
                'customer_state': request.POST.get('customer_state'),
                'customer_zip_code': request.POST.get('customer_zip_code'),
            }
            cinetpay_api = CinetPayAPI()
            result = cinetpay_api.initiate_payment(order, customer_data)
            if result['success']:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'redirect_url': result['payment_url']})
                return redirect(result['payment_url'])
            else:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': result['error']})
                messages.error(request, f"Erreur de paiement: {result['error']}")
        return render(request, 'shop/payment.html', {'order': order, 'user_profile': getattr(request.user, 'profile', None) if request.user.is_authenticated else None})
    except Exception as e:
        logger.error(f"Erreur shop_payment: {e}")
        messages.error(request, 'Erreur lors du processus de paiement')
        return redirect('shop_home')

@csrf_exempt
def shop_cinetpay_notification(request):
    if request.method == 'POST':
        try:
            if request.content_type == 'application/json':
                notification_data = json.loads(request.body)
            else:
                notification_data = request.POST.dict()
            logger.info(f"Notification CinetPay reçue: {notification_data}")
            success = handle_cinetpay_notification(notification_data)
            if success:
                return HttpResponse('OK', status=200)
            return HttpResponse('Error', status=400)
        except Exception as e:
            logger.error(f"Erreur dans shop_cinetpay_notification: {e}")
            return HttpResponse('Error', status=500)
    return HttpResponse('Method not allowed', status=405)

def shop_payment_success(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id)
        if hasattr(order, 'cinetpay_transaction') and order.cinetpay_transaction.status == 'completed':
            order.payment_status = 'paid'
            order.save()
        return render(request, 'shop/payment_success.html', {'order': order})
    except Exception as e:
        logger.error(f"Erreur shop_payment_success: {e}")
        messages.error(request, 'Erreur lors de la confirmation de paiement')
        return redirect('shop_home')

def shop_payment_failed(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id)
        return render(request, 'shop/payment_failed.html', {'order': order})
    except Exception as e:
        logger.error(f"Erreur shop_payment_failed: {e}")
        messages.error(request, "Erreur lors de l'affichage de l'échec")
        return redirect('shop_home')

@login_required
def my_orders(request):
    try:
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        paginator = Paginator(orders, 10)
        page_number = request.GET.get('page')
        orders = paginator.get_page(page_number)
        return render(request, 'shop/my_orders.html', {'orders': orders})
    except Exception as e:
        logger.error(f"Erreur my_orders: {e}")
        messages.error(request, 'Erreur lors du chargement des commandes')
        return redirect('shop_home')

@login_required
def order_detail(request, order_id):
    try:
        order = get_object_or_404(Order, id=order_id, user=request.user)
        return render(request, 'shop/order_detail.html', {'order': order})
    except Exception as e:
        logger.error(f"Erreur order_detail: {e}")
        messages.error(request, 'Commande non trouvée')
        return redirect('my_orders')

@login_required
def sync_shopify_products(request):
    if not request.user.is_staff:
        messages.error(request, 'Accès non autorisé')
        return redirect('index')
    try:
        count = sync_products_from_shopify()
        messages.success(request, f"{count} produits synchronisés depuis Shopify")
    except Exception as e:
        logger.error(f"Erreur sync_shopify_products: {e}")
        messages.error(request, f"Erreur lors de la synchronisation: {e}")
    return redirect('shop_home')

# ===== Paramétrage des infos de paiement vendeur (stubs) =====

@login_required
def seller_payment_setup(request):
    payment_info, _ = SellerPaymentInfo.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        payment_info.preferred_payment_method = request.POST.get('preferred_payment_method', payment_info.preferred_payment_method)
        payment_info.phone_number = request.POST.get('phone_number', payment_info.phone_number)
        payment_info.operator = request.POST.get('operator', payment_info.operator)
        payment_info.country = request.POST.get('country', payment_info.country)
        payment_info.save()
        messages.success(request, 'Informations de paiement mises à jour')
        return redirect('seller_payment_setup')
    return render(request, 'seller_payment_setup.html', {'payment_info': payment_info})

@login_required
def reset_payment_info(request):
    payment_info, _ = SellerPaymentInfo.objects.get_or_create(user=request.user)
    payment_info.delete()
    messages.success(request, 'Informations de paiement réinitialisées')
    return redirect('seller_payment_setup')

# ===== HIGHLIGHTS SYSTEM =====

def highlights_home(request):
    """Page d'accueil des Highlights avec navigation"""
    try:
        # Récupérer quelques highlights récents pour l'aperçu
        recent_highlights = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile').order_by('-created_at')[:10]
        
        # Statistiques pour l'utilisateur connecté
        user_stats = {}
        if request.user.is_authenticated:
            user_stats = {
                'highlights_count': Highlight.objects.filter(author=request.user, is_active=True).count(),
                'subscribers_count': request.user.subscribers.count(),
                'subscriptions_count': request.user.subscriptions.count(),
            }
        
        context = {
            'recent_highlights': recent_highlights,
            'user_stats': user_stats,
        }
        return render(request, 'highlights/home.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_home: {e}")
        messages.error(request, "Erreur lors du chargement des Highlights")
        return redirect('index')

def highlights_for_you(request):
    """Feed personnalisé des Highlights"""
    try:
        highlights = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile').prefetch_related(
            'appreciations', 'comments', 'views'
        ).order_by('-created_at')
        
        # Si l'utilisateur est connecté, prioriser les highlights des abonnements
        if request.user.is_authenticated:
            subscribed_users = request.user.subscriptions.values_list('subscribed_to', flat=True)
            highlights = highlights.annotate(
                is_from_subscription=Exists(
                    UserSubscription.objects.filter(
                        subscriber=request.user,
                        subscribed_to=OuterRef('author')
                    )
                )
            ).order_by('-is_from_subscription', '-created_at')
        
        paginator = Paginator(highlights, 20)
        page_number = request.GET.get('page')
        highlights = paginator.get_page(page_number)
        
        # Ajouter les appréciations utilisateur et compteurs pour chaque highlight
        if request.user.is_authenticated:
            for highlight in highlights:
                highlight.user_appreciation = HighlightAppreciation.objects.filter(
                    highlight=highlight,
                    user=request.user
                ).first()
                highlight.appreciation_counts = highlight.get_appreciation_counts_by_level()
        
        context = {
            'highlights': highlights,
            'page_title': 'Highlights',
        }
        return render(request, 'highlights/feed.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_for_you: {e}")
        messages.error(request, "Erreur lors du chargement du feed")
        return redirect('highlights_home')

@login_required
def highlights_friends(request):
    """Highlights des amis/abonnements uniquement"""
    try:
        subscribed_users = request.user.subscriptions.values_list('subscribed_to', flat=True)
        
        highlights = Highlight.objects.filter(
            author__in=subscribed_users,
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile').prefetch_related(
            'appreciations', 'comments', 'views'
        ).order_by('-created_at')
        
        paginator = Paginator(highlights, 20)
        page_number = request.GET.get('page')
        highlights = paginator.get_page(page_number)
        
        # Ajouter les appréciations utilisateur et compteurs pour chaque highlight
        for highlight in highlights:
            highlight.user_appreciation = HighlightAppreciation.objects.filter(
                highlight=highlight,
                user=request.user
            ).first()
            highlight.appreciation_counts = highlight.get_appreciation_counts_by_level()
        
        context = {
            'highlights': highlights,
            'page_title': 'Amis',
        }
        return render(request, 'highlights/feed.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_friends: {e}")
        messages.error(request, "Erreur lors du chargement des highlights d'amis")
        return redirect('highlights_home')

def highlights_search(request):
    """Recherche de Highlights par hashtags ou utilisateurs"""
    try:
        query = request.GET.get('q', '').strip()
        highlights = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile')
        
        if query:
            if query.startswith('#'):
                # Recherche par hashtag
                hashtag = query[1:].lower()
                highlights = highlights.filter(hashtags__icontains=hashtag)
            else:
                # Recherche par utilisateur ou caption
                highlights = highlights.filter(
                    Q(author__username__icontains=query) |
                    Q(caption__icontains=query)
                )
        
        paginator = Paginator(highlights, 20)
        page_number = request.GET.get('page')
        highlights = paginator.get_page(page_number)
        
        # Hashtags populaires
        popular_hashtags = []
        try:
            all_hashtags = []
            for h in Highlight.objects.filter(is_active=True, expires_at__gt=timezone.now()).values_list('hashtags', flat=True):
                if h:
                    all_hashtags.extend(h)
            
            from collections import Counter
            hashtag_counts = Counter(all_hashtags)
            popular_hashtags = [tag for tag, count in hashtag_counts.most_common(10)]
        except Exception:
            pass
        
        context = {
            'highlights': highlights,
            'query': query,
            'popular_hashtags': popular_hashtags,
            'page_title': 'Recherche',
        }
        return render(request, 'highlights/search.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_search: {e}")
        messages.error(request, "Erreur lors de la recherche")
        return redirect('highlights_home')

def highlights_hashtag(request, hashtag):
    """Highlights pour un hashtag spécifique"""
    try:
        highlights = Highlight.objects.filter(
            hashtags__icontains=hashtag.lower(),
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile').order_by('-created_at')
        
        paginator = Paginator(highlights, 20)
        page_number = request.GET.get('page')
        highlights = paginator.get_page(page_number)
        
        context = {
            'highlights': highlights,
            'hashtag': hashtag,
            'page_title': f'#{hashtag}',
        }
        return render(request, 'highlights/hashtag.html', context)
    except Exception as e:
        logger.error(f"Erreur highlights_hashtag: {e}")
        messages.error(request, "Erreur lors du chargement du hashtag")
        return redirect('highlights_search')

@login_required
def create_highlight(request):
    """Créer un nouveau Highlight"""
    try:
        if request.method == 'POST':
            video = request.FILES.get('video')
            caption = request.POST.get('caption', '').strip()
            
            if not video:
                messages.error(request, 'Veuillez sélectionner une vidéo')
                return render(request, 'highlights/create.html')
            
            # Extraire les hashtags de la caption
            hashtags = re.findall(r'#(\w+)', caption.lower())
            
            # Créer le highlight
            highlight = Highlight.objects.create(
                author=request.user,
                video=video,
                caption=caption,
                hashtags=hashtags
            )
            
            messages.success(request, 'Highlight créé avec succès!')
            return redirect('highlight_detail', highlight_id=highlight.id)
        
        return render(request, 'highlights/create.html')
    except Exception as e:
        logger.error(f"Erreur create_highlight: {e}")
        messages.error(request, "Erreur lors de la création du Highlight")
        return redirect('highlights_home')

def highlight_detail(request, highlight_id):
    """Détail d'un Highlight avec commentaires"""
    try:
        highlight = get_object_or_404(
            Highlight.objects.select_related('author', 'author__profile'),
            id=highlight_id,
            is_active=True
        )
        
        # Vérifier si le highlight n'est pas expiré
        if highlight.is_expired:
            messages.warning(request, "Ce Highlight a expiré")
            return redirect('highlights_home')
        
        # Enregistrer la vue
        if request.user.is_authenticated:
            HighlightView.objects.get_or_create(
                highlight=highlight,
                user=request.user,
                defaults={'ip_address': request.META.get('REMOTE_ADDR')}
            )
        
        # Récupérer les commentaires
        comments = highlight.comments.select_related('user', 'user__profile').order_by('-created_at')
        
        # Vérifier si l'utilisateur a apprécié
        user_appreciation = None
        if request.user.is_authenticated:
            user_appreciation = highlight.appreciations.filter(user=request.user).first()
        
        # Navigation précédent/suivant (par date de création)
        now = timezone.now()
        previous_highlight = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=now,
            created_at__gt=highlight.created_at
        ).order_by('created_at').first()
        next_highlight = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=now,
            created_at__lt=highlight.created_at
        ).order_by('-created_at').first()
        
        context = {
            'highlight': highlight,
            'comments': comments,
            'user_appreciation': user_appreciation,
            'previous_highlight': previous_highlight,
            'next_highlight': next_highlight,
        }
        return render(request, 'highlights/detail.html', context)
    except Exception as e:
        logger.error(f"Erreur highlight_detail: {e}")
        messages.error(request, "Highlight non trouvé")
        return redirect('highlights_home')

@login_required
def delete_highlight(request, highlight_id):
    """Supprimer un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, author=request.user)
        
        if request.method == 'POST':
            highlight.delete()
            messages.success(request, 'Highlight supprimé avec succès')
            return redirect('highlights_home')
        
        return render(request, 'highlights/confirm_delete.html', {'highlight': highlight})
    except Exception as e:
        logger.error(f"Erreur delete_highlight: {e}")
        messages.error(request, "Erreur lors de la suppression")
        return redirect('highlights_home')

@login_required
@require_POST
def toggle_highlight_appreciation(request, highlight_id):
    """Ajouter ou modifier l'appréciation d'un highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        appreciation_level = int(request.POST.get('appreciation_level', 0))
        
        if appreciation_level not in [1, 2, 3, 4, 5, 6]:
            return JsonResponse({'error': 'Niveau d\'appréciation invalide'}, status=400)
        
        # Vérifier si l'utilisateur a déjà apprécié
        existing_appreciation = HighlightAppreciation.objects.filter(
            highlight=highlight,
            user=request.user
        ).first()
        
        if existing_appreciation:
            # Mettre à jour l'appréciation existante
            old_level = existing_appreciation.appreciation_level
            existing_appreciation.appreciation_level = appreciation_level
            existing_appreciation.save()
            
            # Mettre à jour le score de l'auteur
            author_profile = highlight.author.profile
            # Annuler l'ancien impact
            old_impact = {
                1: -10, 2: -4, 3: 2, 4: 4, 5: 6, 6: 10
            }.get(old_level, 0)
            # Ajouter le nouvel impact
            new_impact = {
                1: -10, 2: -4, 3: 2, 4: 4, 5: 6, 6: 10
            }.get(appreciation_level, 0)
            
            author_profile.score = author_profile.score - old_impact + new_impact
            author_profile.save()
            
        else:
            # Créer une nouvelle appréciation
            HighlightAppreciation.objects.create(
                highlight=highlight,
                user=request.user,
                appreciation_level=appreciation_level
            )
            
            # Mettre à jour le score de l'auteur
            author_profile = highlight.author.profile
            author_profile.update_score_from_appreciation(appreciation_level)
        
        # Calculer les statistiques d'appréciation
        appreciations = highlight.appreciations.all()
        appreciation_stats = {}
        for level in range(1, 7):
            count = appreciations.filter(appreciation_level=level).count()
            appreciation_stats[f'level_{level}'] = count
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'appreciation_level': appreciation_level,
                'appreciation_stats': appreciation_stats,
                'total_appreciations': appreciations.count()
            })
        
        return redirect('highlight_detail', highlight_id=highlight.id)
    except Exception as e:
        logger.error(f"Erreur toggle_highlight_appreciation: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def add_highlight_comment(request, highlight_id):
    """Ajouter un commentaire à un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        content = request.POST.get('content', '').strip()
        
        if not content:
            return JsonResponse({'success': False, 'error': 'Commentaire vide'})
        
        comment = HighlightComment.objects.create(
            highlight=highlight,
            user=request.user,
            content=content
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'comment': {
                    'id': str(comment.id),
                    'content': comment.content,
                    'user': comment.user.username,
                    'created_at': comment.created_at.strftime('%H:%M'),
                    'user_avatar': comment.user.profile.profileimg.url if hasattr(comment.user, 'profile') and comment.user.profile.profileimg else None
                },
                'comments_count': highlight.comments_count
            })
        
        return redirect('highlight_detail', highlight_id=highlight.id)
    except Exception as e:
        logger.error(f"Erreur add_highlight_comment: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def share_highlight(request, highlight_id):
    """Partager un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        shared_to_id = request.POST.get('shared_to')
        
        shared_to = None
        if shared_to_id:
            shared_to = get_object_or_404(User, id=shared_to_id)
        
        share = HighlightShare.objects.create(
            highlight=highlight,
            user=request.user,
            shared_to=shared_to
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Highlight partagé'})
        
        messages.success(request, 'Highlight partagé avec succès')
        return redirect('highlight_detail', highlight_id=highlight.id)
    except Exception as e:
        logger.error(f"Erreur share_highlight: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
def record_highlight_view(request, highlight_id):
    """Enregistrer une vue sur un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        
        if request.user.is_authenticated:
            view, created = HighlightView.objects.get_or_create(
                highlight=highlight,
                user=request.user,
                defaults={'ip_address': request.META.get('REMOTE_ADDR')}
            )
        else:
            # Pour les utilisateurs anonymes, utiliser l'IP
            ip_address = request.META.get('REMOTE_ADDR')
            if ip_address:
                view, created = HighlightView.objects.get_or_create(
                    highlight=highlight,
                    ip_address=ip_address,
                    user=None
                )
        
        return JsonResponse({'success': True, 'views_count': highlight.views.count()})
    except Exception as e:
        logger.error(f"Erreur record_highlight_view: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@require_POST
def toggle_subscription(request, user_id):
    """S'abonner/Se désabonner d'un utilisateur"""
    try:
        target_user = get_object_or_404(User, id=user_id)
        
        if target_user == request.user:
            return JsonResponse({'success': False, 'error': 'Impossible de s\'abonner à soi-même'})
        
        subscription, created = UserSubscription.objects.get_or_create(
            subscriber=request.user,
            subscribed_to=target_user
        )
        
        if not created:
            subscription.delete()
            subscribed = False
            action = 'désabonné'
        else:
            subscribed = True
            action = 'abonné'
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'subscribed': subscribed,
                'action': action,
                'subscribers_count': target_user.subscribers.count()
            })
        
        messages.success(request, f'Vous êtes maintenant {action} à {target_user.username}')
        return redirect('profile', username=target_user.username)
    except Exception as e:
        logger.error(f"Erreur toggle_subscription: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def my_subscriptions(request):
    """Liste des abonnements de l'utilisateur"""
    try:
        subscriptions = UserSubscription.objects.filter(
            subscriber=request.user
        ).select_related('subscribed_to', 'subscribed_to__profile').order_by('-created_at')
        
        context = {
            'subscriptions': subscriptions,
        }
        return render(request, 'highlights/subscriptions.html', context)
    except Exception as e:
        logger.error(f"Erreur my_subscriptions: {e}")
        messages.error(request, "Erreur lors du chargement des abonnements")
        return redirect('highlights_home')

@login_required
def my_subscribers(request):
    """Liste des abonnés de l'utilisateur"""
    try:
        subscribers = UserSubscription.objects.filter(
            subscribed_to=request.user
        ).select_related('subscriber', 'subscriber__profile').order_by('-created_at')
        
        context = {
            'subscribers': subscribers,
        }
        return render(request, 'highlights/subscribers.html', context)
    except Exception as e:
        logger.error(f"Erreur my_subscribers: {e}")
        messages.error(request, "Erreur lors du chargement des abonnés")
        return redirect('highlights_home')

# ===== API HIGHLIGHTS (AJAX) =====

def highlights_feed_api(request):
    """API pour le feed des Highlights (AJAX) avec analytics"""
    try:
        page = int(request.GET.get('page', 1))
        feed_type = request.GET.get('type', 'for_you')
        
        highlights = Highlight.objects.filter(
            is_active=True,
            expires_at__gt=timezone.now()
        ).select_related('author', 'author__profile').prefetch_related(
            'appreciations', 'comments', 'views'
        )
        
        # Smart discovery algorithm
        if feed_type == 'for_you' and request.user.is_authenticated:
            # Prioritize based on user engagement patterns
            user_liked_hashtags = get_user_preferred_hashtags(request.user)
            user_interactions = get_user_interaction_history(request.user)
            
            # Apply intelligent sorting
            highlights = apply_discovery_algorithm(highlights, request.user, user_liked_hashtags, user_interactions)
        elif feed_type == 'friends' and request.user.is_authenticated:
            subscribed_users = request.user.subscriptions.values_list('subscribed_to', flat=True)
            highlights = highlights.filter(author__in=subscribed_users)
        
        highlights = highlights.order_by('-created_at')
        
        paginator = Paginator(highlights, 10)
        highlights_page = paginator.get_page(page)
        
        highlights_data = []
        for highlight in highlights_page:
            user_appreciated = None
            if request.user.is_authenticated:
                user_appreciated = highlight.appreciations.filter(user=request.user).first()
            
            # Enhanced analytics data
            engagement_rate = calculate_engagement_rate(highlight)
            view_duration_avg = get_average_view_duration(highlight)
            
            highlights_data.append({
                'id': str(highlight.id),
                'video_url': highlight.video.url,
                'caption': highlight.caption,
                'hashtags': highlight.hashtags,
                'author': {
                    'username': highlight.author.username,
                    'avatar': highlight.author.profile.profileimg.url if hasattr(highlight.author, 'profile') and highlight.author.profile.profileimg else None
                },
                'appreciations_count': highlight.appreciations_count,
                'comments_count': highlight.comments_count,
                'views_count': highlight.views.count(),
                'user_appreciated': user_appreciated.appreciation_level if user_appreciated else None,
                'created_at': highlight.created_at.strftime('%H:%M'),
                'time_remaining': str(highlight.time_remaining) if highlight.time_remaining else None,
                'engagement_rate': engagement_rate,
                'avg_view_duration': view_duration_avg,
                'performance_score': calculate_performance_score(highlight)
            })
        
        return JsonResponse({
            'success': True,
            'highlights': highlights_data,
            'has_next': highlights_page.has_next(),
            'next_page': highlights_page.next_page_number() if highlights_page.has_next() else None,
            'analytics': {
                'total_highlights': highlights.count(),
                'avg_engagement': calculate_average_engagement(highlights_page),
                'trending_hashtags': get_trending_hashtags()
            }
        })
    except Exception as e:
        logger.error(f"Erreur highlights_feed_api: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

def highlight_comments_api(request, highlight_id):
    """API pour les commentaires d'un Highlight"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        comments = highlight.comments.select_related('user', 'user__profile').order_by('-created_at')
        
        comments_data = []
        for comment in comments:
            comments_data.append({
                'id': str(comment.id),
                'content': comment.content,
                'user': {
                    'username': comment.user.username,
                    'avatar': comment.user.profile.profileimg.url if hasattr(comment.user, 'profile') and comment.user.profile.profileimg else None
                },
                'created_at': comment.created_at.strftime('%H:%M')
            })
        
        return JsonResponse({
            'success': True,
            'comments': comments_data
        })
    except Exception as e:
        logger.error(f"Erreur highlight_comments_api: {e}")
        return JsonResponse({'success': False, 'error': str(e)})

# ===== ANALYTICS AND PERFORMANCE HELPERS =====

def get_user_preferred_hashtags(user, limit=10):
    """Get user's preferred hashtags based on interaction history"""
    try:
        # Get hashtags from highlights the user liked
        liked_highlights = Highlight.objects.filter(
            appreciations__user=user,
            is_active=True
        ).values_list('hashtags', flat=True)
        
        all_hashtags = []
        for hashtag_list in liked_highlights:
            if hashtag_list:
                all_hashtags.extend(hashtag_list)
        
        from collections import Counter
        hashtag_counts = Counter(all_hashtags)
        return [tag for tag, count in hashtag_counts.most_common(limit)]
    except Exception as e:
        logger.error(f"Error getting user preferred hashtags: {e}")
        return []

def get_user_interaction_history(user):
    """Get user's interaction patterns for recommendation algorithm"""
    try:
        from django.db.models import Count
        
        # Get users the current user interacts with most
        interacted_users = User.objects.filter(
            Q(highlights__appreciations__user=user) |
            Q(highlights__comments__user=user)
        ).annotate(
            interaction_count=Count('highlights__appreciations') + Count('highlights__comments')
        ).order_by('-interaction_count')[:20]
        
        return list(interacted_users.values_list('id', flat=True))
    except Exception as e:
        logger.error(f"Error getting user interaction history: {e}")
        return []

def apply_discovery_algorithm(highlights_queryset, user, preferred_hashtags, interaction_users):
    """Apply smart discovery algorithm to sort highlights"""
    try:
        from django.db.models import Case, When, IntegerField, F
        
        # Create scoring conditions
        hashtag_score = Case(
            *[When(hashtags__icontains=tag, then=5) for tag in preferred_hashtags[:5]],
            default=0,
            output_field=IntegerField()
        )
        
        interaction_score = Case(
            When(author__id__in=interaction_users[:10], then=3),
            default=0,
            output_field=IntegerField()
        )
        
        # Apply scoring and sort
        return highlights_queryset.annotate(
            discovery_score=hashtag_score + interaction_score
        ).order_by('-discovery_score', '-created_at')
        
    except Exception as e:
        logger.error(f"Error applying discovery algorithm: {e}")
        return highlights_queryset.order_by('-created_at')

def calculate_engagement_rate(highlight):
    """Calculate engagement rate for a highlight"""
    try:
        views_count = highlight.views.count()
        if views_count == 0:
            return 0.0
        
        engagements = highlight.appreciations_count + highlight.comments_count
        return round((engagements / views_count) * 100, 2)
    except Exception as e:
        logger.error(f"Error calculating engagement rate: {e}")
        return 0.0

def get_average_view_duration(highlight):
    """Get average view duration for a highlight (placeholder for future implementation)"""
    # This would require tracking actual view durations
    # For now, return a simulated value based on engagement
    try:
        base_duration = 8.0  # seconds
        engagement_multiplier = min(calculate_engagement_rate(highlight) / 10, 2.0)
        return round(base_duration * (1 + engagement_multiplier), 1)
    except Exception:
        return 8.0

def calculate_performance_score(highlight):
    """Calculate overall performance score for a highlight"""
    try:
        engagement_rate = calculate_engagement_rate(highlight)
        views_count = highlight.views.count()
        recency_score = max(0, 100 - (timezone.now() - highlight.created_at).days * 10)
        
        # Weighted score calculation
        score = (
            engagement_rate * 0.4 +  # 40% engagement
            min(views_count / 10, 50) * 0.3 +  # 30% views (capped at 50)
            recency_score * 0.3  # 30% recency
        )
        
        return round(score, 1)
    except Exception as e:
        logger.error(f"Error calculating performance score: {e}")
        return 0.0

def calculate_average_engagement(highlights_page):
    """Calculate average engagement for a page of highlights"""
    try:
        if not highlights_page:
            return 0.0
        
        total_engagement = sum(calculate_engagement_rate(h) for h in highlights_page)
        return round(total_engagement / len(highlights_page), 2)
    except Exception as e:
        logger.error(f"Error calculating average engagement: {e}")
        return 0.0

def get_trending_hashtags(limit=10):
    """Get currently trending hashtags"""
    try:
        from collections import Counter
        
        # Get hashtags from recent highlights (last 24 hours)
        recent_highlights = Highlight.objects.filter(
            is_active=True,
            created_at__gte=timezone.now() - timezone.timedelta(hours=24)
        ).values_list('hashtags', flat=True)
        
        all_hashtags = []
        for hashtag_list in recent_highlights:
            if hashtag_list:
                all_hashtags.extend(hashtag_list)
        
        hashtag_counts = Counter(all_hashtags)
        return [{'tag': tag, 'count': count} for tag, count in hashtag_counts.most_common(limit)]
    except Exception as e:
        logger.error(f"Error getting trending hashtags: {e}")
        return []

# Enhanced view recording with duration tracking
@require_POST
def record_highlight_view_enhanced(request, highlight_id):
    """Enhanced view recording with duration and analytics"""
    try:
        highlight = get_object_or_404(Highlight, id=highlight_id, is_active=True)
        view_duration = request.POST.get('duration', 0)  # Duration in seconds
        
        if request.user.is_authenticated:
            view, created = HighlightView.objects.get_or_create(
                highlight=highlight,
                user=request.user,
                defaults={
                    'ip_address': request.META.get('REMOTE_ADDR'),
                    'view_duration': float(view_duration) if view_duration else 0
                }
            )
            
            # Update duration if view already exists
            if not created and view_duration:
                view.view_duration = max(view.view_duration or 0, float(view_duration))
                view.save()
        else:
            # For anonymous users, use IP
            ip_address = request.META.get('REMOTE_ADDR')
            if ip_address:
                view, created = HighlightView.objects.get_or_create(
                    highlight=highlight,
                    ip_address=ip_address,
                    user=None,
                    defaults={'view_duration': float(view_duration) if view_duration else 0}
                )
        
        return JsonResponse({
            'success': True,
            'views_count': highlight.views.count(),
            'engagement_rate': calculate_engagement_rate(highlight)
        })
    except Exception as e:
        logger.error(f"Erreur record_highlight_view_enhanced: {e}")
        return JsonResponse({'success': False, 'error': str(e)})
