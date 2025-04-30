// Main JavaScript file for CTF Platform

document.addEventListener('DOMContentLoaded', function() {
    // Enable tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Enable popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Add event listener to delete buttons to show confirmation modal
    var deleteButtons = document.querySelectorAll('.btn-delete');
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(event) {
            event.preventDefault();

            // Get the target modal
            var target = this.getAttribute('data-bs-target');
            var modalElement = document.querySelector(target);

            // Ensure that no modal is in an active state before opening the next one
            if (!modalElement.classList.contains('show')) {
                // If modal is not already shown, show it
                var bsModal = new bootstrap.Modal(modalElement);
                bsModal.show();
            }
        });
    });
    
    // Add event listener to submission forms to show loading spinner
    var flagForms = document.querySelectorAll('.flag-form');
    flagForms.forEach(function(form) {
        form.addEventListener('submit', function() {
            showLoadingSpinner('Submitting flag...');
        });
    });
    
    // Show countdown timers for competitions
    updateCompetitionCountdowns();
    setInterval(updateCompetitionCountdowns, 1000);
    
    // Highlight code blocks
    document.querySelectorAll('pre code').forEach(function(block) {
        if (window.hljs) {
            hljs.highlightBlock(block);
        }
    });
});

// Function to show loading spinner
function showLoadingSpinner(message) {
    var spinnerOverlay = document.createElement('div');
    spinnerOverlay.className = 'spinner-overlay';
    spinnerOverlay.innerHTML = `
        <div class="spinner-container">
            <div class="spinner-border text-light" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
            <div class="spinner-text">${message || 'Loading...'}</div>
        </div>
    `;
    document.body.appendChild(spinnerOverlay);
}

// Function to hide loading spinner
function hideLoadingSpinner() {
    var spinnerOverlay = document.querySelector('.spinner-overlay');
    if (spinnerOverlay) {
        spinnerOverlay.remove();
    }
}

// Function to update competition countdowns
function updateCompetitionCountdowns() {
    var countdowns = document.querySelectorAll('.competition-countdown');
    countdowns.forEach(function(element) {
        var endTime = new Date(element.getAttribute('data-end-time')).getTime();
        var now = new Date().getTime();
        var distance = endTime - now;
        
        if (distance <= 0) {
            element.innerHTML = 'Ended';
            element.classList.add('text-danger');
        } else {
            var days = Math.floor(distance / (1000 * 60 * 60 * 24));
            var hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            var minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
            var seconds = Math.floor((distance % (1000 * 60)) / 1000);
            
            var timeStr = '';
            if (days > 0) {
                timeStr += days + 'd ';
            }
            if (hours > 0 || days > 0) {
                timeStr += hours + 'h ';
            }
            if (minutes > 0 || hours > 0 || days > 0) {
                timeStr += minutes + 'm ';
            }
            timeStr += seconds + 's';
            
            element.innerHTML = timeStr;
        }
    });
}

// Function to copy text to clipboard
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('Copied to clipboard!');
    }, function(err) {
        console.error('Could not copy text: ', err);
    });
}

// Function to show toast notification
function showToast(message, type = 'success') {
    var toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    var toastElement = document.createElement('div');
    toastElement.className = `toast align-items-center text-white bg-${type} border-0`;
    toastElement.setAttribute('role', 'alert');
    toastElement.setAttribute('aria-live', 'assertive');
    toastElement.setAttribute('aria-atomic', 'true');
    
    toastElement.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;
    
    toastContainer.appendChild(toastElement);
    var toast = new bootstrap.Toast(toastElement, { delay: 3000 });
    toast.show();
}
