/**
 * Mobile Responsive Manager for v0.3.0
 */
class MobileResponsiveManager {
    constructor() {
        this.isMobile = false;
        this.sidebarOpen = false;
        this.touchStartX = 0;
        this.touchStartY = 0;
        this.longPressTimer = null;

        this.init();
    }

    init() {
        this.detectDevice();
        this.setupHamburgerMenu();
        this.setupTouchHandlers();
        this.setupKeyboardHandlers();
        this.applyLayout();
    }

    detectDevice() {
        // Check user agent for iPhone 15 Pro Max and other mobile devices
        const userAgent = navigator.userAgent.toLowerCase();
        const isIPhone = /iphone/.test(userAgent);
        const isAndroid = /android/.test(userAgent);
        const isIPad = /ipad/.test(userAgent);

        // Check for user override from settings
        const savedMode = localStorage.getItem('claude-web-ui');
        if (savedMode) {
            const settings = JSON.parse(savedMode);
            if (settings.uiMode === 'mobile') {
                this.isMobile = true;
            } else if (settings.uiMode === 'desktop') {
                this.isMobile = false;
            } else {
                // Auto-detect
                this.isMobile = isIPhone || isAndroid || (isIPad && window.innerWidth < 768);
            }
        } else {
            this.isMobile = isIPhone || isAndroid || (isIPad && window.innerWidth < 768);
        }

        // Add mobile class to body
        if (this.isMobile) {
            document.body.classList.add('mobile');
            document.body.classList.remove('desktop');
        } else {
            document.body.classList.add('desktop');
            document.body.classList.remove('mobile');
        }
    }

    setupHamburgerMenu() {
        // Create hamburger button if it doesn't exist
        if (!document.getElementById('hamburgerMenu')) {
            const hamburger = document.createElement('button');
            hamburger.id = 'hamburgerMenu';
            hamburger.className = 'hamburger-menu';
            hamburger.innerHTML = `
                <span class="hamburger-line"></span>
                <span class="hamburger-line"></span>
                <span class="hamburger-line"></span>
            `;
            document.body.appendChild(hamburger);

            // Create backdrop
            const backdrop = document.createElement('div');
            backdrop.id = 'sidebarBackdrop';
            backdrop.className = 'sidebar-backdrop';
            document.body.appendChild(backdrop);

            // Event handlers
            hamburger.addEventListener('click', () => this.toggleSidebar());
            backdrop.addEventListener('click', () => this.closeSidebar());
        }

        // Hide sidebar on mobile by default
        if (this.isMobile) {
            const sidebar = document.getElementById('sidebar');
            if (sidebar) {
                sidebar.classList.add('collapsed');
            }
        }
    }

    toggleSidebar() {
        const sidebar = document.getElementById('sidebar');
        const backdrop = document.getElementById('sidebarBackdrop');
        const hamburger = document.getElementById('hamburgerMenu');

        if (!sidebar) return;

        this.sidebarOpen = !this.sidebarOpen;

        if (this.sidebarOpen) {
            sidebar.classList.add('active');
            backdrop.classList.add('active');
            hamburger.classList.add('active');
        } else {
            sidebar.classList.remove('active');
            backdrop.classList.remove('active');
            hamburger.classList.remove('active');
        }
    }

    closeSidebar() {
        if (this.sidebarOpen) {
            this.toggleSidebar();
        }
    }

    setupTouchHandlers() {
        if (!this.isMobile) return;

        // Long press for message actions
        document.addEventListener('touchstart', (e) => {
            const messageEl = e.target.closest('.message');
            if (!messageEl) return;

            this.touchStartX = e.touches[0].clientX;
            this.touchStartY = e.touches[0].clientY;

            this.longPressTimer = setTimeout(() => {
                this.showMessageActions(messageEl, e.touches[0]);
            }, 300);
        });

        document.addEventListener('touchend', () => {
            if (this.longPressTimer) {
                clearTimeout(this.longPressTimer);
                this.longPressTimer = null;
            }
        });

        document.addEventListener('touchmove', (e) => {
            if (this.longPressTimer) {
                const deltaX = Math.abs(e.touches[0].clientX - this.touchStartX);
                const deltaY = Math.abs(e.touches[0].clientY - this.touchStartY);

                if (deltaX > 10 || deltaY > 10) {
                    clearTimeout(this.longPressTimer);
                    this.longPressTimer = null;
                }
            }
        });
    }

    showMessageActions(messageEl, touch) {
        // Haptic feedback (if supported)
        if (navigator.vibrate) {
            navigator.vibrate(50);
        }

        // Create context menu
        const existingMenu = document.querySelector('.message-context-menu');
        if (existingMenu) {
            existingMenu.remove();
        }

        const menu = document.createElement('div');
        menu.className = 'message-context-menu';

        const isUserMessage = messageEl.classList.contains('user-message');
        const actions = isUserMessage
            ? ['Copy', 'Edit', 'Delete']
            : ['Copy', 'Retry', 'Continue'];

        actions.forEach(action => {
            const button = document.createElement('button');
            button.textContent = action;
            button.onclick = () => {
                this.handleMessageAction(messageEl, action);
                menu.remove();
            };
            menu.appendChild(button);
        });

        // Position menu
        menu.style.position = 'fixed';
        let x = touch.clientX;
        let y = touch.clientY;

        // Adjust position if near edges
        document.body.appendChild(menu);
        const rect = menu.getBoundingClientRect();

        if (x + rect.width > window.innerWidth) {
            x = window.innerWidth - rect.width - 10;
        }
        if (y + rect.height > window.innerHeight) {
            y = window.innerHeight - rect.height - 10;
        }

        menu.style.left = `${x}px`;
        menu.style.top = `${y}px`;

        // Close on outside click
        setTimeout(() => {
            document.addEventListener('click', function closeMenu() {
                menu.remove();
                document.removeEventListener('click', closeMenu);
            });
        }, 100);
    }

    handleMessageAction(messageEl, action) {
        const messageId = messageEl.dataset.messageId;
        const content = messageEl.querySelector('.message-content')?.textContent;

        switch(action) {
            case 'Copy':
                navigator.clipboard.writeText(content);
                window.showToast('Message copied to clipboard');
                break;
            case 'Edit':
                window.messageManager?.editMessage(messageId);
                break;
            case 'Delete':
                window.messageManager?.deleteMessage(messageId);
                break;
            case 'Retry':
                window.messageManager?.retryMessage(messageId);
                break;
            case 'Continue':
                window.messageManager?.continueFromMessage(messageId);
                break;
        }
    }

    setupKeyboardHandlers() {
        if (!this.isMobile) return;

        const inputField = document.getElementById('messageInput');
        if (!inputField) return;

        // Handle keyboard show/hide
        let initialHeight = window.innerHeight;

        window.addEventListener('resize', () => {
            const currentHeight = window.innerHeight;
            const inputContainer = document.querySelector('.input-container');

            if (currentHeight < initialHeight * 0.75) {
                // Keyboard is shown
                inputContainer?.classList.add('keyboard-visible');
            } else {
                // Keyboard is hidden
                inputContainer?.classList.remove('keyboard-visible');
            }
        });
    }

    applyLayout() {
        // Handle file chips on mobile
        if (this.isMobile) {
            this.setupMobileFileChips();
        }
    }

    setupMobileFileChips() {
        const fileDisplay = document.getElementById('selectedFilesDisplay');
        if (!fileDisplay) return;

        // Replace full chips with badge on mobile
        if (this.isMobile) {
            const chipsContainer = document.getElementById('fileChipsContainer');
            const fileCount = chipsContainer?.querySelectorAll('.file-chip').length || 0;

            if (fileCount > 0) {
                // Create badge
                const badge = document.createElement('div');
                badge.className = 'file-count-badge';
                badge.innerHTML = `📎 ${fileCount}`;
                badge.onclick = () => this.showFileModal();

                // Hide original chips, show badge
                chipsContainer.style.display = 'none';

                const badgeContainer = document.createElement('div');
                badgeContainer.id = 'mobileBadgeContainer';
                badgeContainer.appendChild(badge);
                fileDisplay.appendChild(badgeContainer);
            }
        }
    }

    showFileModal() {
        // Create modal to show file list
        const modal = document.createElement('div');
        modal.className = 'file-list-modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Attached Files</h3>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="modal-body">
                    <div id="modalFileList"></div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Populate file list
        const fileList = document.getElementById('modalFileList');
        const chips = document.querySelectorAll('.file-chip');

        chips.forEach(chip => {
            const fileItem = document.createElement('div');
            fileItem.className = 'modal-file-item';
            fileItem.innerHTML = `
                <span class="file-name">${chip.querySelector('.chip-text').textContent}</span>
                <span class="file-tokens">${chip.querySelector('.chip-tokens').textContent}</span>
            `;
            fileList.appendChild(fileItem);
        });

        // Close handler
        modal.querySelector('.close-modal').onclick = () => {
            modal.remove();
        };

        modal.onclick = (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        };
    }
}

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
    window.mobileManager = new MobileResponsiveManager();
});
