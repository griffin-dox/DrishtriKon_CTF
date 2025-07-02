// static/js/contact-form.js
// Handles reCAPTCHA v3 for the contact form

document.addEventListener('DOMContentLoaded', function() {
    const contactForm = document.getElementById('contactForm');
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            if (window.recaptcha) {
                window.recaptcha.executeAction('contact', function(token) {
                    document.getElementById('recaptchaToken').value = token;
                    contactForm.submit();
                });
            } else {
                contactForm.submit();
            }
        });
    }
});
