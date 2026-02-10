// static/js/fake-login.js
// This script records input without actually submitting data
document.addEventListener('DOMContentLoaded', function() {
    var loginForm = document.getElementById('loginForm');
    if (!loginForm) return;
    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        // Log the attempt (in a real system, this would send to server)
        console.log('Honeypot login attempt:', { username, password });
        // Show fake error
        document.getElementById('errorMessage').textContent = 'Invalid credentials. Please try again.';
        // Clear password field as a real system would
        document.getElementById('password').value = '';
        // Record the attempt via a hidden image request
        const trackerImg = new Image();
        trackerImg.src = '/admin/track?u=' + encodeURIComponent(username) + '&p=' + encodeURIComponent(password);
        return false;
    });
});
