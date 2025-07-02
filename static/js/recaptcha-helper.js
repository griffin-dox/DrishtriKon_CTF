// static/js/recaptcha-helper.js
// Global reCAPTCHA helper functions
window.recaptcha = {
    siteKey: window.RECAPTCHA_SITE_KEY || '',
    executeAction: function(action, callback) {
        if (typeof grecaptcha !== 'undefined' && grecaptcha.ready) {
            grecaptcha.ready(function() {
                grecaptcha.execute(window.RECAPTCHA_SITE_KEY, {action: action}).then(function(token) {
                    if (callback) callback(token);
                });
            });
        } else {
            console.warn('reCAPTCHA not loaded, proceeding without token');
            if (callback) callback('');
        }
    }
};
