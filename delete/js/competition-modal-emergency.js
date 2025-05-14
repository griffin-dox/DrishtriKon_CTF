/**
 * Emergency fix for competition modals
 * This script completely rewrites how modals work for delete confirmations
 */
document.addEventListener('DOMContentLoaded', function() {
    // Apply emergency modal fixes
    applyEmergencyModalFixes();
    
    // Enhance delete buttons
    enhanceDeleteButtons();
});

/**
 * Apply emergency fixes to all modals
 */
function applyEmergencyModalFixes() {
    // Remove all transition effects from modals that might cause flickering
    const styleTag = document.createElement('style');
    styleTag.textContent = `
        .modal, .modal-dialog, .modal-content, .modal-backdrop {
            transition: none !important;
            animation: none !important;
        }
        
        .modal.fade .modal-dialog {
            transform: none !important;
        }
        
        .modal.show {
            display: block !important;
            opacity: 1 !important;
        }
        
        /* Force pointer events on everything */
        .modal *, .modal-dialog *, .modal-content * {
            pointer-events: auto !important;
        }
        
        /* Higher z-index for delete modals */
        .delete-confirmation-modal {
            z-index: 2000 !important;
        }
        
        .delete-confirmation-modal .modal-dialog {
            z-index: 2001 !important;
        }
        
        .delete-confirmation-modal .modal-content {
            z-index: 2002 !important;
        }
    `;
    document.head.appendChild(styleTag);
}

/**
 * Add special handling for delete buttons
 */
function enhanceDeleteButtons() {
    const deleteButtons = document.querySelectorAll('.btn-delete, button[data-bs-toggle="modal"]');
    
    deleteButtons.forEach(button => {
        // Make delete button more prominent
        button.style.position = 'relative';
        button.style.zIndex = '10';
        
        // Get the target modal
        const targetId = button.getAttribute('data-bs-target');
        if (!targetId) return;
        
        const modal = document.querySelector(targetId);
        if (!modal) return;
        
        // Add class for styling
        modal.classList.add('delete-confirmation-modal');
        
        // Make sure modals have static backdrop
        if (modal.getAttribute('data-bs-backdrop') !== 'static') {
            modal.setAttribute('data-bs-backdrop', 'static');
            modal.setAttribute('data-bs-keyboard', 'false');
        }
        
        // Fix the radio buttons
        const radioButtons = modal.querySelectorAll('input[type="radio"]');
        if (radioButtons.length > 0) {
            // Make sure at least one is checked
            const anyChecked = Array.from(radioButtons).some(r => r.checked);
            if (!anyChecked) {
                radioButtons[0].checked = true;
            }
            
            // Extra special treatment for radio buttons
            radioButtons.forEach(radio => {
                // Fix positioning and z-index
                radio.style.position = 'relative';
                radio.style.zIndex = '20';
                
                // Find parent form if any
                const form = radio.closest('form');
                if (!form) return;
                
                // Make sure we have a hidden input to track the selection
                let hiddenInput = form.querySelector('input[type="hidden"][name="challenge_action"]');
                if (!hiddenInput) {
                    hiddenInput = document.createElement('input');
                    hiddenInput.type = 'hidden';
                    hiddenInput.name = 'challenge_action';
                    form.appendChild(hiddenInput);
                }
                
                // Set initial value
                if (radio.checked) {
                    hiddenInput.value = radio.value;
                }
                
                // Update on change
                radio.addEventListener('change', function() {
                    hiddenInput.value = this.value;
                });
            });
        }
        
        // Ensure any forms inside the modal submit properly
        const forms = modal.querySelectorAll('form');
        forms.forEach(form => {
            // Style the form and buttons
            form.style.position = 'relative';
            form.style.zIndex = '15';
            
            const deleteBtn = form.querySelector('.btn-danger');
            if (deleteBtn) {
                deleteBtn.style.position = 'relative';
                deleteBtn.style.zIndex = '25';
                deleteBtn.classList.add('delete-confirm-btn');
            }
        });
    });
}