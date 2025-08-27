// Système de notification pour alerter les vendeurs
document.addEventListener('DOMContentLoaded', function() {
    // Vérifier si l'utilisateur est connecté et pas sur une page de chat
    if (document.body.classList.contains('logged-in') && !document.body.classList.contains('chat-page')) {
        // Initialiser le compteur de notifications
        let previousCount = 0;
        
        // Créer l'élément audio pour la notification sonore
        const notificationSound = new Audio('/static/sounds/notification.mp3');
        
        // Créer l'indicateur de notification
        const notificationIndicator = document.createElement('div');
        notificationIndicator.className = 'notification-indicator';
        notificationIndicator.innerHTML = `
            <span class="notification-count">0</span>
            <a href="/notifications/" class="notification-link">
                <i class="fas fa-bell"></i>
            </a>
        `;
        document.body.appendChild(notificationIndicator);
        
        // Mettre à jour le compteur de notification dans le menu déroulant
        function updateNotificationCountInMenu() {
            fetch('/notifications/unread/count/')
                .then(response => response.json())
                .then(data => {
                    const menuCountElement = document.getElementById('notification-count-menu');
                    if (menuCountElement) {
                        menuCountElement.textContent = data.count;
                        if (data.count > 0) {
                            menuCountElement.style.display = 'inline-block';
                        } else {
                            menuCountElement.style.display = 'none';
                        }
                    }
                })
                .catch(error => {
                    console.error('Erreur lors de la mise à jour du compteur de notification:', error);
                });
        }
        
        // Mettre à jour le compteur dans le menu toutes les 30 secondes
        updateNotificationCountInMenu();
        setInterval(updateNotificationCountInMenu, 30000);
        
        // Fonction pour vérifier les nouvelles notifications
        function checkNotifications() {
            fetch('/notifications/unread/count/')
                .then(response => response.json())
                .then(data => {
                    const count = data.count;
                    const countElement = document.querySelector('.notification-count');
                    
                    // Mettre à jour le compteur
                    if (count > 0) {
                        countElement.textContent = count;
                        notificationIndicator.classList.add('has-notifications');
                        
                        // Jouer un son si de nouvelles notifications sont arrivées
                        if (count > previousCount) {
                            notificationSound.play().catch(error => {
                                console.log('Erreur lors de la lecture du son:', error);
                            });
                            
                            // Afficher une notification visuelle
                            showNotificationPopup(count - previousCount);
                        }
                    } else {
                        countElement.textContent = '0';
                        notificationIndicator.classList.remove('has-notifications');
                    }
                    
                    previousCount = count;
                })
                .catch(error => {
                    console.error('Erreur lors de la vérification des notifications:', error);
                });
        }
        
        // Fonction pour afficher une notification visuelle
        function showNotificationPopup(newCount) {
            const popup = document.createElement('div');
            popup.className = 'notification-popup';
            popup.innerHTML = `
                <div class="notification-popup-content">
                    <i class="fas fa-bell"></i>
                    <p>Vous avez ${newCount} nouvelle${newCount > 1 ? 's' : ''} notification${newCount > 1 ? 's' : ''}!</p>
                </div>
            `;
            document.body.appendChild(popup);
            
            // Animer l'apparition
            setTimeout(() => {
                popup.classList.add('show');
            }, 100);
            
            // Supprimer après quelques secondes
            setTimeout(() => {
                popup.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(popup);
                }, 500);
            }, 5000);
        }
        
        // Vérifier les notifications immédiatement et toutes les 30 secondes
        checkNotifications();
        setInterval(checkNotifications, 30000);
    }
});
