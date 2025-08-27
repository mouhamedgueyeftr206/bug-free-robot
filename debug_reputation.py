#!/usr/bin/env python
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'socialgame.settings')
django.setup()

from django.contrib.auth.models import User
from blizzgame.models import UserReputation, Post
from blizzgame.reputation_utils import get_user_reputation_summary, create_transaction_rating

def check_reputation_data():
    print("=== DIAGNOSTIC DES INSIGNES BLIZZ ===\n")
    
    # Vérifier les utilisateurs
    users = User.objects.all()[:5]  # Prendre les 5 premiers utilisateurs
    print(f"Nombre d'utilisateurs: {User.objects.count()}")
    
    for user in users:
        print(f"\n--- Utilisateur: {user.username} ---")
        
        # Vérifier la réputation
        try:
            reputation = UserReputation.objects.get(user=user)
            print(f"Réputation trouvée:")
            print(f"  - Transactions vendeur: {reputation.seller_total_transactions}")
            print(f"  - Transactions réussies: {reputation.seller_successful_transactions}")
            print(f"  - Score vendeur: {reputation.seller_score}")
        except UserReputation.DoesNotExist:
            print("  - Aucune réputation trouvée")
        
        # Vérifier le résumé de réputation
        summary = get_user_reputation_summary(user)
        print(f"Résumé de réputation:")
        print(f"  - Total transactions vendeur: {summary['seller']['total_transactions']}")
        print(f"  - Score vendeur: {summary['seller']['score']}")
        print(f"  - Badge vendeur: {summary['seller']['badge']}")
        
        # Vérifier les posts de l'utilisateur
        posts_count = Post.objects.filter(author=user).count()
        print(f"  - Nombre de posts: {posts_count}")

def create_test_data():
    print("\n=== CRÉATION DE DONNÉES DE TEST ===\n")
    
    # Prendre le premier utilisateur
    user = User.objects.first()
    if not user:
        print("Aucun utilisateur trouvé!")
        return
    
    print(f"Création de données de test pour: {user.username}")
    
    # Simuler quelques transactions réussies
    from blizzgame.models import Transaction
    from django.utils import timezone
    
    # Créer une transaction fictive pour tester
    try:
        # Créer des évaluations de test
        from blizzgame.reputation_utils import update_user_reputation
        
        # Forcer la mise à jour de la réputation
        reputation = update_user_reputation(user)
        
        # Ajouter manuellement quelques transactions réussies pour le test
        reputation.seller_total_transactions = 10
        reputation.seller_successful_transactions = 8
        reputation.seller_failed_transactions = 1
        reputation.seller_fraudulent_transactions = 1
        reputation.save()
        
        # Recalculer le score et le badge
        reputation.update_reputation()
        
        print(f"Données de test créées:")
        print(f"  - Total transactions: {reputation.seller_total_transactions}")
        print(f"  - Transactions réussies: {reputation.seller_successful_transactions}")
        print(f"  - Score: {reputation.seller_score}")
        print(f"  - Badge: {reputation.seller_badge_level}")
        
    except Exception as e:
        print(f"Erreur lors de la création des données de test: {e}")

if __name__ == "__main__":
    check_reputation_data()
    
    # Demander si on veut créer des données de test
    create_test = input("\nVoulez-vous créer des données de test? (y/n): ")
    if create_test.lower() == 'y':
        create_test_data()
        print("\n=== VÉRIFICATION APRÈS CRÉATION ===")
        check_reputation_data()
