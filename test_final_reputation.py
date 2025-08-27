#!/usr/bin/env python
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'socialgame.settings')
django.setup()

from blizzgame.badge_config import get_seller_badge

def test_final_reputation_system():
    """Test du système de réputation final avec facteur Maître ajusté à 0.83"""
    
    print("=== SYSTÈME DE RÉPUTATION VENDEUR FINAL ===\n")
    print("Formule: Score Final = (Réussies/Total) × 100 × min(Total/10, 1.0) × Facteur Badge\n")
    print("Facteurs: Bronze=1.0, Argent=0.6, Or=0.7, Maître=0.83")
    print("Seuils: Bronze=0%, Argent=60%, Or=70%, Maître=80%")
    print("Objectif: Être Maître Vendeur à partir de 96% de réussite\n")
    
    # Cas de test focalisés sur l'objectif 96%
    test_cases = [
        # (réussies, total, description)
        (1, 1, "Nouveau vendeur - 1 vente parfaite"),
        (5, 5, "Vendeur débutant - 5 ventes parfaites"),
        (8, 10, "Vendeur établi - 8/10 ventes (80%)"),
        (9, 10, "Vendeur établi - 9/10 ventes (90%)"),
        (10, 10, "Vendeur expérimenté - 10/10 ventes (100%)"),
        (19, 20, "Vendeur expert - 19/20 ventes (95%)"),
        (48, 50, "Vendeur test - 48/50 ventes (96%) ⭐ OBJECTIF"),
        (49, 50, "Vendeur test - 49/50 ventes (98%)"),
        (95, 100, "Vendeur légendaire - 95/100 ventes (95%)"),
        (96, 100, "Vendeur légendaire - 96/100 ventes (96%) ⭐ OBJECTIF"),
        (98, 100, "Vendeur légendaire - 98/100 ventes (98%)"),
        (100, 100, "Vendeur parfait - 100/100 ventes (100%)"),
    ]
    
    print("| Réussies | Total | Base% | Conf | Vol% | Badge Pot. | Fact | Final% | Badge Final | Objectif |")
    print("|----------|-------|-------|------|------|------------|------|--------|-------------|----------|")
    
    for successful, total, description in test_cases:
        # Calcul selon la formule finale
        base_score = (successful / total) * 100
        confidence_threshold = 10
        confidence_factor = min(total / confidence_threshold, 1.0)
        volume_adjusted_score = base_score * confidence_factor
        
        # Obtenir le badge potentiel et son facteur
        potential_badge = get_seller_badge(volume_adjusted_score)
        badge_factor = potential_badge.get('factor', 1.0) if potential_badge else 1.0
        
        # Score final avec facteur de badge
        final_score = volume_adjusted_score * badge_factor
        
        # Badge final
        final_badge = get_seller_badge(final_score)
        final_name = final_badge['name'] if final_badge else "Aucun"
        
        # Vérifier si l'objectif est atteint
        is_96_percent = base_score == 96.0
        is_master = "Maître" in final_name
        objective_status = "✅ RÉUSSI" if (is_96_percent and is_master) else ("🎯 TEST" if is_96_percent else "")
        
        print(f"| {successful:8} | {total:5} | {base_score:5.1f} | {confidence_factor:4.1f} | {volume_adjusted_score:4.1f} | {potential_badge['name'][:10] if potential_badge else 'Aucun':10} | {badge_factor:4.2f} | {final_score:6.1f} | {final_name:11} | {objective_status:8} |")
    
    print(f"\n=== VÉRIFICATION DE L'OBJECTIF ===")
    
    # Test spécifique pour 96%
    test_96_cases = [
        (48, 50, "48/50 ventes"),
        (96, 100, "96/100 ventes"),
        (192, 200, "192/200 ventes"),
    ]
    
    print("\nTest spécifique pour 96% de réussite:")
    all_master = True
    
    for successful, total, desc in test_96_cases:
        base_score = (successful / total) * 100
        confidence_factor = min(total / 10, 1.0)
        volume_adjusted_score = base_score * confidence_factor
        potential_badge = get_seller_badge(volume_adjusted_score)
        badge_factor = potential_badge.get('factor', 1.0) if potential_badge else 1.0
        final_score = volume_adjusted_score * badge_factor
        final_badge = get_seller_badge(final_score)
        final_name = final_badge['name'] if final_badge else "Aucun"
        is_master = "Maître" in final_name
        
        status = "✅ MAÎTRE" if is_master else "❌ ÉCHEC"
        print(f"- {desc}: {base_score}% → {final_score:.1f}% → {final_name} {status}")
        
        if not is_master:
            all_master = False
    
    print(f"\n🎯 RÉSULTAT FINAL: {'✅ OBJECTIF ATTEINT' if all_master else '❌ AJUSTEMENT NÉCESSAIRE'}")
    if all_master:
        print("Le système permet maintenant d'être Maître Vendeur à partir de 96% de réussite!")
    else:
        print("Le facteur nécessite encore un ajustement pour atteindre l'objectif.")

if __name__ == "__main__":
    test_final_reputation_system()
