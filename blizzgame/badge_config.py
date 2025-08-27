"""
Configuration des badges pour le système de réputation BLIZZ
Focus uniquement sur les vendeurs - Badges visuels personnalisés
"""

# Définir les badges vendeurs uniquement (insignes IA sans texte pour compatibilité internationale)
SELLER_BADGES = [
    {
        'name': 'Vendeur Bronze',  # Nom affiché dans l'interface (traduit selon la langue)
        'level': 'bronze', 
        'min_score': 0, 
        'color': '#CD7F32', 
        'icon': 'bronze_badge.png',  # Insigne sans texte (icône étoile simple)
        'description': 'Vendeur débutant',
        'icon_symbol': '⭐',  # Fallback emoji si l'image ne charge pas
        'tier': 1
    },
    {
        'name': 'Vendeur Argent', 
        'level': 'silver', 
        'min_score': 60,  # Nouveau seuil avec facteur 0.6
        'color': '#C0C0C0', 
        'icon': 'silver_badge.png',  # Insigne sans texte (icône double étoile)
        'description': 'Vendeur confirmé',
        'icon_symbol': '⭐⭐',
        'tier': 2,
        'factor': 0.6  # Facteur de pondération
    },
    {
        'name': 'Vendeur Or', 
        'level': 'gold', 
        'min_score': 70,  # Nouveau seuil avec facteur 0.7
        'color': '#FFD700', 
        'icon': 'gold_badge.png',  # Insigne sans texte (icône couronne)
        'description': 'Vendeur expert',
        'icon_symbol': '👑',
        'tier': 3,
        'factor': 0.7  # Facteur de pondération
    },
    {
        'name': 'Maître Vendeur', 
        'level': 'diamond', 
        'min_score': 80,  # Seuil ajusté pour être atteint à 96% (96% * 0.83 = 79.68%)
        'color': '#6C5CE7', 
        'icon': 'diamond_badge.png',  # Insigne sans texte (icône éclair/diamant)
        'description': 'Vendeur légendaire',
        'icon_symbol': '⚡💎',
        'tier': 4,
        'factor': 0.84  # Facteur final pour Maître à 96% (96% * 0.84 = 80.64%)
    },
]

# Traductions des noms de badges (extensible pour d'autres langues)
BADGE_TRANSLATIONS = {
    'fr': {
        'bronze': 'Vendeur Bronze',
        'silver': 'Vendeur Argent', 
        'gold': 'Vendeur Or',
        'diamond': 'Maître Vendeur'
    },
    'en': {
        'bronze': 'Bronze Seller',
        'silver': 'Silver Seller',
        'gold': 'Gold Seller', 
        'diamond': 'Master Seller'
    },
    'es': {
        'bronze': 'Vendedor Bronce',
        'silver': 'Vendedor Plata',
        'gold': 'Vendedor Oro',
        'diamond': 'Vendedor Maestro'
    }
}

def get_seller_badge(score):
    """Retourne le badge approprié selon le score vendeur"""
    if score is None or score < 0:
        return SELLER_BADGES[0]  # Bronze par défaut
    
    # Trouver le badge le plus élevé correspondant au score
    appropriate_badge = SELLER_BADGES[0]
    for badge in SELLER_BADGES:
        if score >= badge['min_score']:
            appropriate_badge = badge
        else:
            break
    
    return appropriate_badge

def get_badge_by_level(level):
    """Retourne un badge par son niveau"""
    for badge in SELLER_BADGES:
        if badge['level'] == level:
            return badge
    return SELLER_BADGES[0]  # Bronze par défaut

def get_translated_badge_name(badge, language='fr'):
    """Retourne le nom du badge traduit selon la langue spécifiée"""
    if language in BADGE_TRANSLATIONS and badge['level'] in BADGE_TRANSLATIONS[language]:
        return BADGE_TRANSLATIONS[language][badge['level']]
    return badge['name']  # Fallback vers le nom français par défaut

def get_seller_badge_with_translation(score, language='fr'):
    """Retourne le badge avec le nom traduit selon la langue"""
    badge = get_seller_badge(score)
    if badge:
        # Créer une copie du badge avec le nom traduit
        translated_badge = badge.copy()
        translated_badge['name'] = get_translated_badge_name(badge, language)
        return translated_badge
    return badge
