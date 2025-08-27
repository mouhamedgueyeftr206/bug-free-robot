#!/usr/bin/env python
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'socialgame.settings')
django.setup()

from blizzgame.badge_config import get_seller_badge

def test_new_reputation_system():
    """Test du nouveau système de réputation avec facteur de confiance"""
    
    print("=== NOUVEAU SYSTÈME DE RÉPUTATION VENDEUR ===\n")
    print("Formule: Score Final = (Réussies/Total) × 100 × min(Total/10, 1.0)\n")
    
    # Cas de test avec différents scénarios
    test_cases = [
        # (réussies, total, description)
        (1, 1, "Nouveau vendeur - 1 vente parfaite"),
        (2, 2, "Nouveau vendeur - 2 ventes parfaites"),
        (5, 5, "Vendeur débutant - 5 ventes parfaites"),
        (8, 10, "Vendeur établi - 8/10 ventes"),
        (9, 10, "Vendeur établi - 9/10 ventes"),
        (10, 10, "Vendeur expérimenté - 10/10 ventes"),
        (15, 20, "Vendeur expérimenté - 15/20 ventes"),
        (19, 20, "Vendeur expert - 19/20 ventes"),
        (48, 50, "Vendeur maître - 48/50 ventes"),
        (3, 5, "Vendeur débutant - 3/5 ventes"),
        (1, 3, "Vendeur débutant - 1/3 ventes"),
    ]
    
    print("| Réussies | Total | Score Base | Facteur | Score Final | Badge |")
    print("|----------|-------|------------|---------|-------------|-------|")
    
    for successful, total, description in test_cases:
        # Calcul selon la nouvelle formule
        base_score = (successful / total) * 100
        confidence_threshold = 10
        confidence_factor = min(total / confidence_threshold, 1.0)
        final_score = base_score * confidence_factor
        
        # Obtenir le badge correspondant
        badge = get_seller_badge(final_score)
        badge_name = badge['name'] if badge else "Aucun"
        
        print(f"| {successful:8} | {total:5} | {base_score:8.1f}% | {confidence_factor:7.1f} | {final_score:9.1f}% | {badge_name} |")
    
    print(f"\n=== ANALYSE DU SYSTÈME ===")
    print("✅ Avantages du nouveau système:")
    print("- Évite les scores artificiellement élevés pour les nouveaux vendeurs")
    print("- Encourage l'accumulation d'expérience (volume de ventes)")
    print("- Maintient l'équité pour les vendeurs expérimentés")
    print("- Le facteur de confiance atteint 100% à partir de 10 ventes")
    
    print(f"\n📊 Exemples concrets:")
    print("- 1 vente parfaite → 10% (Bronze) au lieu de 100% (Maître)")
    print("- 5 ventes parfaites → 50% (Bronze) au lieu de 100% (Maître)")
    print("- 8/10 ventes → 80% (Argent) - score réaliste")
    print("- 19/20 ventes → 95% (Maître) - mérite le niveau maximum")

if __name__ == "__main__":
    test_new_reputation_system()
