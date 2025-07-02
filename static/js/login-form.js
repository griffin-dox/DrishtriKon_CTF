// static/js/login-form.js
// Handles reCAPTCHA v3 for the login form

document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (window.recaptcha) {
                window.recaptcha.executeAction('login', function(token) {
                    document.getElementById('recaptchaToken').value = token;
                    loginForm.submit();
                });
            } else {
                loginForm.submit();
            }
        });
    }
});
