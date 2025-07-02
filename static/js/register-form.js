// static/js/register-form.js
// Handles reCAPTCHA v3 for the register form

document.addEventListener('DOMContentLoaded', function() {
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (window.recaptcha) {
                window.recaptcha.executeAction('register', function(token) {
                    document.getElementById('recaptchaToken').value = token;
                    registerForm.submit();
                });
            } else {
                registerForm.submit();
            }
        });
    }
});
