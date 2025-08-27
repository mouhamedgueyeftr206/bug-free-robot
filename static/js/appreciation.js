class AppreciationSystem {
    constructor() {
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupImageProtection();
    }

    setupEventListeners() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('.appreciation-button')) {
                const button = e.target.closest('.appreciation-button');
                const level = button.dataset.level;
                const highlightId = button.dataset.highlightId;
                
                if (level && highlightId) {
                    this.handleAppreciation(highlightId, parseInt(level), button);
                }
            }
        });
    }

    setupImageProtection() {
        document.addEventListener('contextmenu', (e) => {
            if (e.target.classList.contains('appreciation-emoji')) {
                e.preventDefault();
                return false;
            }
        });

        document.addEventListener('dragstart', (e) => {
            if (e.target.classList.contains('appreciation-emoji')) {
                e.preventDefault();
                return false;
            }
        });
    }

    async handleAppreciation(highlightId, level, button) {
        try {
            this.animateButtonClick(button);

            const csrfToken = this.getCSRFToken();
            if (!csrfToken) {
                throw new Error('CSRF token non trouvé');
            }

            const formData = new FormData();
            formData.append('appreciation_level', level);

            const response = await fetch(`/highlights/${highlightId}/appreciate/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            });

            if (response.ok) {
                const data = await response.json();
                
                if (data.success) {
                    this.updateAppreciationUI(highlightId, level, data);
                }
            }
        } catch (error) {
            console.error('Erreur:', error);
        }
    }

    updateAppreciationUI(highlightId, level, data) {
        const container = document.querySelector(`[data-highlight-id="${highlightId}"]`);
        if (!container) return;

        if (level) {
            container.querySelectorAll('.appreciation-button').forEach(btn => {
                btn.classList.remove('selected');
            });

            const selectedButton = container.querySelector(`[data-level="${level}"]`);
            if (selectedButton) {
                selectedButton.classList.add('selected');
            }
        }

        if (data.appreciation_stats) {
            Object.keys(data.appreciation_stats).forEach(levelKey => {
                const count = data.appreciation_stats[levelKey];
                const levelNumber = levelKey.replace('level_', '');
                const button = container.querySelector(`[data-level="${levelNumber}"]`);
                if (button) {
                    const countElement = button.querySelector('.appreciation-count');
                    if (countElement) {
                        countElement.textContent = count;
                    }
                }
            });
        }

        if (data.total_appreciations !== undefined) {
            const totalElement = container.querySelector('.total-appreciations');
            if (totalElement) {
                totalElement.textContent = data.total_appreciations;
            }
        }
    }

    animateButtonClick(button) {
        button.style.transform = 'scale(0.9)';
        setTimeout(() => {
            button.style.transform = 'scale(1.1)';
            setTimeout(() => {
                button.style.transform = 'scale(1)';
            }, 150);
        }, 150);
    }

    getCSRFToken() {
        let token = '';
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken) {
            token = metaToken.getAttribute('content');
        }
        if (!token) {
            const inputToken = document.querySelector('[name=csrfmiddlewaretoken]');
            if (inputToken) {
                token = inputToken.value;
            }
        }
        if (!token) {
            const cookies = document.cookie.split(';');
            for (let cookie of cookies) {
                const [name, value] = cookie.trim().split('=');
                if (name === 'csrftoken') {
                    token = value;
                    break;
                }
            }
        }
        return token;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new AppreciationSystem();
});
