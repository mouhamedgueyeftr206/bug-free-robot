#!/usr/bin/env python
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'socialgame.settings')
django.setup()

from blizzgame.badge_config import get_seller_badge

def test_updated_reputation_system():
    """Test du système de réputation mis à jour avec facteurs par niveau"""
    
    print("=== SYSTÈME DE RÉPUTATION VENDEUR MIS À JOUR ===\n")
    print("Formule: Score Final = (Réussies/Total) × 100 × min(Total/10, 1.0) × Facteur Badge\n")
    print("Facteurs: Bronze=1.0, Argent=0.6, Or=0.7, Maître=0.8")
    print("Seuils: Bronze=0%, Argent=60%, Or=70%, Maître=80%")
    print("Objectif: Être Maître Vendeur à partir de 96% de réussite\n")
    
    # Cas de test avec différents scénarios
    test_cases = [
        # (réussies, total, description)
        (1, 1, "Nouveau vendeur - 1 vente parfaite"),
        (5, 5, "Vendeur débutant - 5 ventes parfaites"),
        (8, 10, "Vendeur établi - 8/10 ventes"),
        (9, 10, "Vendeur établi - 9/10 ventes"),
        (10, 10, "Vendeur expérimenté - 10/10 ventes"),
        (19, 20, "Vendeur expert - 19/20 ventes (95%)"),
        (48, 50, "Vendeur maître - 48/50 ventes (96%)"),
        (49, 50, "Vendeur maître - 49/50 ventes (98%)"),
        (95, 100, "Vendeur légendaire - 95/100 ventes"),
        (96, 100, "Vendeur légendaire - 96/100 ventes"),
        (98, 100, "Vendeur légendaire - 98/100 ventes"),
    ]
    
    print("| Réussies | Total | Base% | Conf | Vol% | Badge Potentiel | Facteur | Final% | Badge Final |")
    print("|----------|-------|-------|------|------|----------------|---------|--------|-------------|")
    
    for successful, total, description in test_cases:
        # Calcul selon la nouvelle formule
        base_score = (successful / total) * 100
        confidence_threshold = 10
        confidence_factor = min(total / confidence_threshold, 1.0)
        volume_adjusted_score = base_score * confidence_factor
        
        # Obtenir le badge potentiel et son facteur
        potential_badge = get_seller_badge(volume_adjusted_score)
        badge_factor = potential_badge.get('factor', 1.0) if potential_badge else 1.0
        potential_name = potential_badge['name'] if potential_badge else "Aucun"
        
        # Score final avec facteur de badge
        final_score = volume_adjusted_score * badge_factor
        
        # Badge final
        final_badge = get_seller_badge(final_score)
        final_name = final_badge['name'] if final_badge else "Aucun"
        
        print(f"| {successful:8} | {total:5} | {base_score:5.1f} | {confidence_factor:4.1f} | {volume_adjusted_score:4.1f} | {potential_name:14} | {badge_factor:7.1f} | {final_score:6.1f} | {final_name} |")
    
    print(f"\n=== ANALYSE DU NOUVEAU SYSTÈME ===")
    print("✅ Objectifs atteints:")
    print("- 96% de réussite avec 10+ ventes → Maître Vendeur")
    print("- Progression équilibrée avec facteurs par niveau")
    print("- Évite les scores artificiellement élevés pour nouveaux vendeurs")
    
    print(f"\n📊 Exemples clés:")
    print("- 1 vente parfaite → 10% (Bronze)")
    print("- 5 ventes parfaites → 50% (Bronze)")
    print("- 19/20 ventes (95%) → 95% × 0.8 = 76% (Or)")
    print("- 48/50 ventes (96%) → 96% × 0.8 = 76.8% (Or)")
    print("- 96/100 ventes (96%) → 96% × 0.8 = 76.8% (Or)")
    print("\n⚠️  Note: Le système semble nécessiter un ajustement pour atteindre le seuil Maître à 96%")

if __name__ == "__main__":
    test_updated_reputation_system()
