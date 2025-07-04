/**
 * CTF Platform Core JavaScript Module
 * Consolidated functionality to eliminate redundancy across pages
 */

// Global CTF App namespace
window.CTFApp = window.CTFApp || {};

// Core utilities module
CTFApp.Utils = {
    // CSRF Token Management
    csrfToken: {
        get: function() {
            const metaToken = document.querySelector('meta[name="csrf-token"]');
            return metaToken ? metaToken.getAttribute('content') : null;
        },
        
        injectToForm: function(form) {
            const token = this.get();
            if (!token) return false;
            
            let csrfInput = form.querySelector('input[name="csrf_token"]');
            if (!csrfInput) {
                csrfInput = document.createElement('input');
                csrfInput.type = 'hidden';
                csrfInput.name = 'csrf_token';
                form.appendChild(csrfInput);
            }
            csrfInput.value = token;
            return true;
        },
        
        injectToAllForms: function() {
            document.querySelectorAll('form').forEach(form => {
                this.injectToForm(form);
            });
        }
    },

    // Loading spinner utilities
    spinner: {
        show: function(message = 'Loading...') {
            this.hide(); // Remove any existing spinner
            
            const spinnerOverlay = document.createElement('div');
            spinnerOverlay.className = 'spinner-overlay';
            spinnerOverlay.innerHTML = `
                <div class="spinner-container">
                    <div class="spinner-border text-light" role="status">
                        <span class="visually-hidden">Loading...</span>
                    </div>
                    <div class="spinner-text">${message}</div>
                </div>
            `;
            document.body.appendChild(spinnerOverlay);
        },
        
        hide: function() {
            const spinner = document.querySelector('.spinner-overlay');
            if (spinner) spinner.remove();
        }
    },

    // Toast notification system
    toast: {
        show: function(message, type = 'success', delay = 3000) {
            let toastContainer = document.querySelector('.toast-container');
            if (!toastContainer) {
                toastContainer = document.createElement('div');
                toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
                document.body.appendChild(toastContainer);
            }
            
            const toastElement = document.createElement('div');
            toastElement.className = `toast align-items-center text-white bg-${type} border-0`;
            toastElement.setAttribute('role', 'alert');
            toastElement.setAttribute('aria-live', 'assertive');
            toastElement.setAttribute('aria-atomic', 'true');
            
            toastElement.innerHTML = `
                <div class="d-flex">
                    <div class="toast-body">${message}</div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                </div>
            `;
            
            toastContainer.appendChild(toastElement);
            const toast = new bootstrap.Toast(toastElement, { delay });
            toast.show();
            
            // Auto-remove after showing
            setTimeout(() => {
                if (toastElement.parentNode) {
                    toastElement.remove();
                }
            }, delay + 500);
        }
    },

    // Clipboard utilities
    clipboard: {
        copy: function(text, successMessage = 'Copied to clipboard!') {
            if (navigator.clipboard) {
                navigator.clipboard.writeText(text).then(() => {
                    CTFApp.Utils.toast.show(successMessage);
                }).catch(err => {
                    console.error('Copy failed:', err);
                    CTFApp.Utils.toast.show('Copy failed', 'danger');
                });
            } else {
                // Fallback for older browsers
                const textArea = document.createElement('textarea');
                textArea.value = text;
                document.body.appendChild(textArea);
                textArea.select();
                try {
                    document.execCommand('copy');
                    CTFApp.Utils.toast.show(successMessage);
                } catch (err) {
                    console.error('Copy fallback failed:', err);
                    CTFApp.Utils.toast.show('Copy failed', 'danger');
                }
                document.body.removeChild(textArea);
            }
        }
    }
};

// Unified Modal System
CTFApp.Modal = {
    activeModal: null,
    backdrop: null,
    
    create: function(options = {}) {
        const {
            id = 'modal-' + Math.random().toString(36).substr(2, 9),
            title = 'Confirm Action',
            body = '',
            buttons = [],
            size = '',
            closeOnBackdrop = true
        } = options;
        
        // Create modal HTML
        const modalHTML = `
            <div class="modal fade" id="${id}" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog ${size}">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close" data-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">${body}</div>
                        <div class="modal-footer">
                            ${buttons.map(btn => `
                                <button type="button" class="btn ${btn.class || 'btn-secondary'}" 
                                        data-action="${btn.action || 'close'}">${btn.text}</button>
                            `).join('')}
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Insert modal into DOM
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        const modal = document.getElementById(id);
        
        // Add event listeners
        this.attachEventListeners(modal, closeOnBackdrop);
        
        return modal;
    },
    
    show: function(modalElement) {
        if (this.activeModal) {
            this.hide(this.activeModal);
        }
        
        this.activeModal = modalElement;
        
        // Create backdrop
        this.backdrop = document.createElement('div');
        this.backdrop.className = 'modal-backdrop fade show';
        document.body.appendChild(this.backdrop);
        
        // Show modal
        modalElement.style.display = 'block';
        modalElement.classList.add('show');
        document.body.classList.add('modal-open');
        document.body.style.overflow = 'hidden';
        
        // Focus management
        setTimeout(() => {
            const firstBtn = modalElement.querySelector('.modal-footer button');
            if (firstBtn) firstBtn.focus();
        }, 100);
    },
    
    hide: function(modalElement) {
        if (!modalElement) return;
        
        modalElement.style.display = 'none';
        modalElement.classList.remove('show');
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        
        if (this.backdrop) {
            this.backdrop.remove();
            this.backdrop = null;
        }
        
        // Remove modal from DOM if it was dynamically created
        if (modalElement.id.startsWith('modal-')) {
            setTimeout(() => modalElement.remove(), 150);
        }
        
        this.activeModal = null;
    },
    
    attachEventListeners: function(modal, closeOnBackdrop) {
        // Close button handlers
        modal.querySelectorAll('[data-dismiss="modal"], [data-action="close"]').forEach(btn => {
            btn.addEventListener('click', () => this.hide(modal));
        });
        
        // Button action handlers
        modal.querySelectorAll('[data-action]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = btn.getAttribute('data-action');
                if (action !== 'close') {
                    const event = new CustomEvent('modal:action', { 
                        detail: { action, button: btn, modal } 
                    });
                    modal.dispatchEvent(event);
                }
            });
        });
        
        // Backdrop click
        if (closeOnBackdrop) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hide(modal);
                }
            });
        }
        
        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.activeModal === modal) {
                this.hide(modal);
            }
        });
    },
    
    // Confirmation dialog helper
    confirm: function(options = {}) {
        const {
            title = 'Confirm Action',
            message = 'Are you sure?',
            confirmText = 'Confirm',
            cancelText = 'Cancel',
            confirmClass = 'btn-danger',
            onConfirm = () => {},
            onCancel = () => {}
        } = options;
        
        const modal = this.create({
            title,
            body: `<p>${message}</p>`,
            buttons: [
                { text: cancelText, class: 'btn-secondary', action: 'cancel' },
                { text: confirmText, class: confirmClass, action: 'confirm' }
            ]
        });
        
        modal.addEventListener('modal:action', (e) => {
            if (e.detail.action === 'confirm') {
                onConfirm();
            } else if (e.detail.action === 'cancel') {
                onCancel();
            }
            this.hide(modal);
        });
        
        this.show(modal);
        return modal;
    }
};

// reCAPTCHA module
CTFApp.ReCaptcha = {
    siteKey: window.RECAPTCHA_SITE_KEY || '',
    
    executeAction: function(action) {
        return new Promise((resolve, reject) => {
            if (typeof grecaptcha !== 'undefined' && grecaptcha.ready) {
                grecaptcha.ready(() => {
                    grecaptcha.execute(this.siteKey, { action })
                        .then(resolve)
                        .catch(reject);
                });
            } else {
                console.warn('reCAPTCHA not loaded, proceeding without token');
                resolve('');
            }
        });
    },
    
    // Form integration helper
    enhanceForm: function(formElement, action = 'submit') {
        if (!formElement) return;
        
        formElement.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            try {
                // Get reCAPTCHA token
                const token = await this.executeAction(action);
                
                // Inject token into form
                let tokenInput = formElement.querySelector('input[name="recaptcha_token"]');
                if (!tokenInput) {
                    tokenInput = document.createElement('input');
                    tokenInput.type = 'hidden';
                    tokenInput.name = 'recaptcha_token';
                    formElement.appendChild(tokenInput);
                }
                tokenInput.value = token;
                
                // Ensure CSRF token is present
                CTFApp.Utils.csrfToken.injectToForm(formElement);
                
                // Submit form
                formElement.submit();
            } catch (error) {
                console.error('reCAPTCHA error:', error);
                CTFApp.Utils.toast.show('Security verification failed', 'danger');
            }
        });
    }
};

// Competition countdown utilities
CTFApp.Countdown = {
    timers: new Map(),
    
    start: function(elementSelector, endTime) {
        const elements = document.querySelectorAll(elementSelector);
        if (elements.length === 0) return;
        
        const timerId = setInterval(() => {
            this.updateCountdowns(elements, new Date(endTime));
        }, 1000);
        
        this.timers.set(elementSelector, timerId);
        
        // Initial update
        this.updateCountdowns(elements, new Date(endTime));
    },
    
    updateCountdowns: function(elements, endTime) {
        const now = new Date().getTime();
        const distance = endTime.getTime() - now;
        
        elements.forEach(element => {
            if (distance <= 0) {
                element.innerHTML = 'Ended';
                element.classList.add('text-danger');
            } else {
                const days = Math.floor(distance / (1000 * 60 * 60 * 24));
                const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((distance % (1000 * 60)) / 1000);
                
                let timeStr = '';
                if (days > 0) timeStr += days + 'd ';
                if (hours > 0 || days > 0) timeStr += hours + 'h ';
                if (minutes > 0 || hours > 0 || days > 0) timeStr += minutes + 'm ';
                timeStr += seconds + 's';
                
                element.innerHTML = timeStr;
            }
        });
        
        // Stop timer if ended
        if (distance <= 0) {
            const timerId = this.timers.get(elements[0].getAttribute('data-selector'));
            if (timerId) {
                clearInterval(timerId);
                this.timers.delete(elements[0].getAttribute('data-selector'));
            }
        }
    },
    
    stop: function(elementSelector) {
        const timerId = this.timers.get(elementSelector);
        if (timerId) {
            clearInterval(timerId);
            this.timers.delete(elementSelector);
        }
    }
};

// Auto-initialization
document.addEventListener('DOMContentLoaded', function() {
    // Inject CSRF tokens to all forms
    CTFApp.Utils.csrfToken.injectToAllForms();
    
    // Initialize Bootstrap components
    if (window.bootstrap) {
        // Tooltips
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
        
        // Popovers
        const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
        popoverTriggerList.map(function(popoverTriggerEl) {
            return new bootstrap.Popover(popoverTriggerEl);
        });
    }
    
    // Initialize countdowns
    document.querySelectorAll('.competition-countdown').forEach(element => {
        const endTime = element.getAttribute('data-end-time');
        if (endTime) {
            CTFApp.Countdown.start(`.competition-countdown[data-end-time="${endTime}"]`, endTime);
        }
    });
    
    // Enhanced delete button handling
    document.querySelectorAll('.btn-delete').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            
            const message = this.getAttribute('data-message') || 'Are you sure you want to delete this item?';
            const form = this.closest('form') || document.querySelector(this.getAttribute('data-form'));
            
            CTFApp.Modal.confirm({
                title: 'Confirm Deletion',
                message: message,
                confirmText: 'Delete',
                confirmClass: 'btn-danger',
                onConfirm: () => {
                    if (form) {
                        CTFApp.Utils.csrfToken.injectToForm(form);
                        form.submit();
                    }
                }
            });
        });
    });
    
    // Enhance forms with reCAPTCHA
    document.querySelectorAll('form[data-recaptcha]').forEach(form => {
        const action = form.getAttribute('data-recaptcha');
        CTFApp.ReCaptcha.enhanceForm(form, action);
    });
});
