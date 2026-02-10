/**
 * Form-specific functionality for CTF platform
 * Handles form validation, submission, and security features
 */

CTFApp.Forms = {
    // Enhanced form submission with loading states
    enhanceForm: function(formSelector, options = {}) {
        const forms = document.querySelectorAll(formSelector);
        
        forms.forEach(form => {
            const {
                loadingMessage = 'Submitting...',
                successMessage = 'Success!',
                showLoading = true,
                preventMultipleSubmit = true,
                validateOnSubmit = true,
                recaptchaAction = null
            } = options;
            
            let isSubmitting = false;
            
            form.addEventListener('submit', async function(e) {
                e.preventDefault();
                
                // Prevent multiple submissions
                if (preventMultipleSubmit && isSubmitting) {
                    return false;
                }
                
                // Client-side validation
                if (validateOnSubmit && !this.checkValidity()) {
                    this.reportValidity();
                    return false;
                }
                
                isSubmitting = true;
                
                try {
                    // Show loading spinner
                    if (showLoading) {
                        CTFApp.Utils.spinner.show(loadingMessage);
                    }
                    
                    // Disable submit buttons
                    const submitBtns = this.querySelectorAll('button[type="submit"], input[type="submit"]');
                    submitBtns.forEach(btn => {
                        btn.disabled = true;
                        if (btn.tagName === 'BUTTON') {
                            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Submitting...';
                        }
                    });
                    
                    // Handle reCAPTCHA if specified
                    if (recaptchaAction) {
                        const token = await CTFApp.ReCaptcha.executeAction(recaptchaAction);
                        let tokenInput = this.querySelector('input[name="recaptcha_token"]');
                        if (!tokenInput) {
                            tokenInput = document.createElement('input');
                            tokenInput.type = 'hidden';
                            tokenInput.name = 'recaptcha_token';
                            this.appendChild(tokenInput);
                        }
                        tokenInput.value = token;
                    }
                    
                    // Ensure CSRF token
                    CTFApp.Utils.csrfToken.injectToForm(this);
                    
                    // Submit form
                    this.submit();
                    
                } catch (error) {
                    console.error('Form submission error:', error);
                    CTFApp.Utils.toast.show('Submission failed. Please try again.', 'danger');
                    
                    // Re-enable form
                    isSubmitting = false;
                    if (showLoading) {
                        CTFApp.Utils.spinner.hide();
                    }
                    
                    const submitBtns = this.querySelectorAll('button[type="submit"], input[type="submit"]');
                    submitBtns.forEach(btn => {
                        btn.disabled = false;
                        if (btn.tagName === 'BUTTON' && btn.hasAttribute('data-original-text')) {
                            btn.innerHTML = btn.getAttribute('data-original-text');
                        }
                    });
                }
            });
            
            // Store original button text for restoration
            const submitBtns = form.querySelectorAll('button[type="submit"]');
            submitBtns.forEach(btn => {
                btn.setAttribute('data-original-text', btn.innerHTML);
            });
        });
    },
    
    // Real-time form validation
    addRealTimeValidation: function(formSelector) {
        const forms = document.querySelectorAll(formSelector);
        
        forms.forEach(form => {
            const inputs = form.querySelectorAll('input, textarea, select');
            
            inputs.forEach(input => {
                // Add validation feedback containers if they don't exist
                if (!input.nextElementSibling || !input.nextElementSibling.classList.contains('invalid-feedback')) {
                    const feedback = document.createElement('div');
                    feedback.className = 'invalid-feedback';
                    input.parentNode.insertBefore(feedback, input.nextSibling);
                }
                
                // Real-time validation on blur
                input.addEventListener('blur', function() {
                    this.validateInput();
                }.bind(this));
                
                // Clear validation on input
                input.addEventListener('input', function() {
                    this.classList.remove('is-invalid', 'is-valid');
                });
            });
        });
    },
    
    validateInput: function(input) {
        const feedbackEl = input.nextElementSibling;
        
        if (input.checkValidity()) {
            input.classList.remove('is-invalid');
            input.classList.add('is-valid');
            if (feedbackEl) feedbackEl.textContent = '';
        } else {
            input.classList.remove('is-valid');
            input.classList.add('is-invalid');
            if (feedbackEl) feedbackEl.textContent = input.validationMessage;
        }
    },
    
    // Flag submission handling for CTF challenges
    initFlagSubmission: function() {
        const flagForms = document.querySelectorAll('.flag-form, form[data-flag-form]');
        
        flagForms.forEach(form => {
            this.enhanceForm(form, {
                loadingMessage: 'Checking flag...',
                recaptchaAction: 'flag_submit',
                validateOnSubmit: true
            });
            
            // Auto-focus flag input
            const flagInput = form.querySelector('input[name="flag"], input[type="text"]');
            if (flagInput && !flagInput.value) {
                flagInput.focus();
            }
            
            // Format flag input (remove spaces, etc.)
            if (flagInput) {
                flagInput.addEventListener('input', function() {
                    // Remove spaces and convert to uppercase for consistency
                    this.value = this.value.replace(/\s/g, '').toUpperCase();
                });
            }
        });
    },
    
    // Contact form enhancements
    initContactForm: function() {
        const contactForm = document.querySelector('#contactForm, form[data-contact-form]');
        if (contactForm) {
            this.enhanceForm(contactForm, {
                loadingMessage: 'Sending message...',
                successMessage: 'Message sent successfully!',
                recaptchaAction: 'contact'
            });
            
            this.addRealTimeValidation(contactForm);
        }
    },
    
    // Login form enhancements
    initLoginForm: function() {
        const loginForm = document.querySelector('#loginForm, form[data-login-form]');
        if (loginForm) {
            this.enhanceForm(loginForm, {
                loadingMessage: 'Signing in...',
                recaptchaAction: 'login'
            });
            
            // Remember me functionality
            const rememberCheckbox = loginForm.querySelector('input[name="remember_me"]');
            if (rememberCheckbox) {
                // Load saved preference
                rememberCheckbox.checked = localStorage.getItem('rememberMe') === 'true';
                
                rememberCheckbox.addEventListener('change', function() {
                    localStorage.setItem('rememberMe', this.checked);
                });
            }
            
            // Auto-focus username field
            const usernameInput = loginForm.querySelector('input[name="username"], input[type="email"]');
            if (usernameInput && !usernameInput.value) {
                usernameInput.focus();
            }
        }
    }
};

// Auto-initialize form features
document.addEventListener('DOMContentLoaded', function() {
    // Initialize based on page content
    CTFApp.Forms.initFlagSubmission();
    CTFApp.Forms.initContactForm();
    CTFApp.Forms.initLoginForm();
    
    // Add general form enhancements to all forms not already handled
    const unhandledForms = document.querySelectorAll('form:not(.flag-form):not(#contactForm):not(#loginForm)');
    unhandledForms.forEach(form => {
        CTFApp.Forms.enhanceForm(form, {
            showLoading: true,
            preventMultipleSubmit: true
        });
    });
});
