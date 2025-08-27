document.addEventListener('DOMContentLoaded', function() {
    // Récupérer les chats actifs de l'utilisateur
    fetchActiveChats();

    // Ajouter le conteneur de chat flottant au body s'il n'existe pas déjà
    if (!document.getElementById('floating-chat-container')) {
        const chatContainer = document.createElement('div');
        chatContainer.id = 'floating-chat-container';
        document.body.appendChild(chatContainer);
    }
});

// Fonction pour récupérer les chats actifs
function fetchActiveChats() {
    fetch('/chats/active/')
        .then(response => response.json())
        .then(data => {
            if (data.chats && data.chats.length > 0) {
                renderChatButtons(data.chats);
            }
        })
        .catch(error => console.error('Erreur lors de la récupération des chats:', error));
}

// Fonction pour afficher les boutons de chat
function renderChatButtons(chats) {
    const container = document.getElementById('floating-chat-container');
    if (!container) return;

    // Vider le conteneur
    container.innerHTML = '';

    // Créer le bouton principal pour afficher/masquer les chats
    const mainButton = document.createElement('div');
    mainButton.className = 'chat-main-button';
    mainButton.innerHTML = `<i class="fas fa-comments"></i> <span class="chat-count">${chats.length}</span>`;
    mainButton.addEventListener('click', toggleChatList);
    container.appendChild(mainButton);

    // Créer la liste des chats
    const chatList = document.createElement('div');
    chatList.className = 'chat-list';
    chatList.style.display = 'none';
    
    chats.forEach(chat => {
        const chatButton = document.createElement('div');
        chatButton.className = 'chat-button';
        chatButton.dataset.chatId = chat.id;
        
        // Déterminer l'autre personne dans le chat
        const otherPerson = chat.is_buyer ? chat.seller_username : chat.buyer_username;
        
        chatButton.innerHTML = `
            <div class="chat-button-avatar">
                <img src="${chat.other_user_profile_img}" alt="${otherPerson}">
                ${chat.unread_count > 0 ? `<span class="unread-badge">${chat.unread_count}</span>` : ''}
            </div>
            <div class="chat-button-info">
                <div class="chat-button-name">${otherPerson}</div>
                <div class="chat-button-title">${chat.post_title}</div>
            </div>
        `;
        
        chatButton.addEventListener('click', function() {
            openChatWindow(chat.id, otherPerson, chat.post_title);
        });
        
        chatList.appendChild(chatButton);
    });
    
    container.appendChild(chatList);
}

// Fonction pour afficher/masquer la liste des chats
function toggleChatList() {
    const chatList = document.querySelector('.chat-list');
    if (chatList) {
        chatList.style.display = chatList.style.display === 'none' ? 'block' : 'none';
    }
}

// Fonction pour ouvrir une fenêtre de chat
function openChatWindow(chatId, otherPerson, postTitle) {
    // Fermer la fenêtre si elle est déjà ouverte
    const existingChat = document.querySelector(`.chat-window[data-chat-id="${chatId}"]`);
    if (existingChat) {
        existingChat.remove();
        return;
    }
    
    // Créer la fenêtre de chat
    const chatWindow = document.createElement('div');
    chatWindow.className = 'chat-window';
    chatWindow.dataset.chatId = chatId;
    
    chatWindow.innerHTML = `
        <div class="chat-window-header">
            <div class="chat-window-title">${postTitle}</div>
            <div class="chat-window-actions">
                <button class="chat-window-minimize"><i class="fas fa-minus"></i></button>
                <button class="chat-window-close"><i class="fas fa-times"></i></button>
            </div>
        </div>
        <div class="chat-window-body">
            <div class="chat-window-messages" id="chat-messages-${chatId}"></div>
        </div>
        <div class="chat-window-footer">
            <form id="chat-form-${chatId}" class="chat-window-form">
                <input type="text" class="chat-window-input" placeholder="Tapez votre message..." required>
                <button type="submit" class="chat-window-send"><i class="fas fa-paper-plane"></i></button>
            </form>
        </div>
    `;
    
    document.body.appendChild(chatWindow);
    
    // Position initiale de la fenêtre
    chatWindow.style.bottom = '20px';
    chatWindow.style.right = '20px';
    
    // Rendre la fenêtre déplaçable
    makeDraggable(chatWindow);
    
    // Charger les messages
    loadChatMessages(chatId);
    
    // Ajouter les écouteurs d'événements
    const minimizeBtn = chatWindow.querySelector('.chat-window-minimize');
    const closeBtn = chatWindow.querySelector('.chat-window-close');
    const form = chatWindow.querySelector(`#chat-form-${chatId}`);
    
    minimizeBtn.addEventListener('click', function() {
        const body = chatWindow.querySelector('.chat-window-body');
        const footer = chatWindow.querySelector('.chat-window-footer');
        
        if (body.style.display === 'none') {
            body.style.display = 'block';
            footer.style.display = 'flex';
            chatWindow.classList.remove('minimized');
        } else {
            body.style.display = 'none';
            footer.style.display = 'none';
            chatWindow.classList.add('minimized');
        }
    });
    
    closeBtn.addEventListener('click', function() {
        chatWindow.remove();
    });
    
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        const input = this.querySelector('.chat-window-input');
        const message = input.value.trim();
        
        if (message) {
            sendChatMessage(chatId, message);
            input.value = '';
        }
    });
}

// Fonction pour charger les messages d'un chat
function loadChatMessages(chatId) {
    fetch(`/chat/${chatId}/messages/`)
        .then(response => response.json())
        .then(data => {
            const messagesContainer = document.getElementById(`chat-messages-${chatId}`);
            if (!messagesContainer) return;
            
            messagesContainer.innerHTML = '';
            
            if (data.messages.length === 0) {
                messagesContainer.innerHTML = '<div class="no-messages">Aucun message. Commencez la conversation!</div>';
                return;
            }
            
            data.messages.forEach(message => {
                const messageEl = document.createElement('div');
                messageEl.className = `chat-message ${message.is_mine ? 'message-mine' : 'message-other'}`;
                
                messageEl.innerHTML = `
                    <div class="message-content">${message.content}</div>
                    <div class="message-meta">
                        <span class="message-sender">${message.sender}</span>
                        <span class="message-time">${message.created_at}</span>
                    </div>
                `;
                
                messagesContainer.appendChild(messageEl);
            });
            
            // Défiler vers le bas
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        })
        .catch(error => console.error('Erreur lors du chargement des messages:', error));
}

// Fonction pour envoyer un message
function sendChatMessage(chatId, content) {
    const formData = new FormData();
    formData.append('content', content);
    
    fetch(`/chat/${chatId}/send/`, {
        method: 'POST',
        body: formData,
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Ajouter le message à la fenêtre de chat
            const messagesContainer = document.getElementById(`chat-messages-${chatId}`);
            if (!messagesContainer) return;
            
            // Supprimer le message "aucun message" s'il existe
            const noMessages = messagesContainer.querySelector('.no-messages');
            if (noMessages) {
                noMessages.remove();
            }
            
            const messageEl = document.createElement('div');
            messageEl.className = 'chat-message message-mine';
            
            messageEl.innerHTML = `
                <div class="message-content">${data.message.content}</div>
                <div class="message-meta">
                    <span class="message-sender">${data.message.sender}</span>
                    <span class="message-time">${data.message.created_at}</span>
                </div>
            `;
            
            messagesContainer.appendChild(messageEl);
            
            // Défiler vers le bas
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
    })
    .catch(error => console.error('Erreur lors de l\'envoi du message:', error));
}

// Fonction pour rendre un élément déplaçable
function makeDraggable(element) {
    let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
    
    const header = element.querySelector('.chat-window-header');
    if (header) {
        header.onmousedown = dragMouseDown;
    }
    
    function dragMouseDown(e) {
        e.preventDefault();
        // Position initiale du curseur
        pos3 = e.clientX;
        pos4 = e.clientY;
        document.onmouseup = closeDragElement;
        document.onmousemove = elementDrag;
    }
    
    function elementDrag(e) {
        e.preventDefault();
        // Calculer la nouvelle position
        pos1 = pos3 - e.clientX;
        pos2 = pos4 - e.clientY;
        pos3 = e.clientX;
        pos4 = e.clientY;
        // Définir la nouvelle position de l'élément
        element.style.top = (element.offsetTop - pos2) + "px";
        element.style.left = (element.offsetLeft - pos1) + "px";
        // Réinitialiser bottom et right pour éviter les conflits
        element.style.bottom = 'auto';
        element.style.right = 'auto';
    }
    
    function closeDragElement() {
        // Arrêter de déplacer quand le bouton de la souris est relâché
        document.onmouseup = null;
        document.onmousemove = null;
    }
}

// Actualiser les chats toutes les 30 secondes
setInterval(fetchActiveChats, 30000);
