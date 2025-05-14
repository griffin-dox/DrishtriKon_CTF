/**
 * Modal Fix Script - Fixes issues with Bootstrap modals
 * Specifically targeting problems with disappearing modals, radio buttons, and form submission
 */
document.addEventListener('DOMContentLoaded', function() {
    // Fix for all modals
    fixAllModals();
    
    // Add specific fixes for delete confirmation modals
    fixDeleteModals();
});

/**
 * Apply fixes to all Bootstrap modals
 */
function fixAllModals() {
    const allModals = document.querySelectorAll('.modal');
    
    allModals.forEach(modal => {
        // Add data-bs-backdrop="static" to prevent modal from closing when clicking outside
        if (!modal.getAttribute('data-bs-backdrop')) {
            modal.setAttribute('data-bs-backdrop', 'static');
        }
        
        // Fix z-index issues
        modal.style.zIndex = '1050';
        
        // Ensure all modal content gets pointer events
        const modalContent = modal.querySelector('.modal-content');
        if (modalContent) {
            modalContent.style.pointerEvents = 'all';
        }
        
        // Fix form controls in modals
        const formControls = modal.querySelectorAll('input, select, textarea, button');
        formControls.forEach(control => {
            control.style.position = 'relative';
            control.style.zIndex = '5';
        });
    });
}

/**
 * Special fixes for delete confirmation modals
 */
function fixDeleteModals() {
    // Find all delete buttons that open modals
    const deleteButtons = document.querySelectorAll('.btn-delete, [data-bs-toggle="modal"]');
    
    deleteButtons.forEach(button => {
        // Make sure the button stays visible
        button.addEventListener('mouseenter', function() {
            this.style.zIndex = '10';
            this.style.position = 'relative';
        });
        
        // Only proceed if this button opens a modal
        if (button.getAttribute('data-bs-toggle') !== 'modal') return;
        
        // Get the associated modal
        const modalId = button.getAttribute('data-bs-target');
        if (!modalId) return;
        
        const modal = document.querySelector(modalId);
        if (!modal) return;
        
        // Add delete-confirmation-modal class for styling
        modal.classList.add('delete-confirmation-modal');
        
        // Fix radio buttons in this modal
        fixRadioButtons(modal);
        
        // Make sure the modal stays visible when interacting with it
        modal.addEventListener('mouseenter', function() {
            this.classList.add('force-show');
            const backdrop = document.querySelector('.modal-backdrop');
            if (backdrop) backdrop.style.opacity = '0.75';
        });
    });
}

/**
 * Fix radio button behavior in modals
 */
function fixRadioButtons(modal) {
    // Get all radio button groups
    const radioGroups = {};
    const radioButtons = modal.querySelectorAll('input[type="radio"]');
    
    radioButtons.forEach(radio => {
        // Group radios by name
        const name = radio.getAttribute('name');
        if (!radioGroups[name]) {
            radioGroups[name] = [];
        }
        radioGroups[name].push(radio);
        
        // Make sure at least one radio is checked
        if (radioGroups[name].length === 1) {
            radio.checked = true;
        }
        
        // Find a form that might need the value
        const nearestForm = radio.closest('form');
        if (nearestForm) {
            const radioName = radio.getAttribute('name');
            
            // Create a hidden input to store the selected value if not already exists
            let hiddenInput = nearestForm.querySelector(`input[name="${radioName}"][type="hidden"]`);
            if (!hiddenInput) {
                hiddenInput = document.createElement('input');
                hiddenInput.type = 'hidden';
                hiddenInput.name = radioName;
                nearestForm.appendChild(hiddenInput);
            }
            
            // Update hidden input when radio changes
            radio.addEventListener('change', function() {
                hiddenInput.value = this.value;
            });
            
            // Initialize with current value
            if (radio.checked) {
                hiddenInput.value = radio.value;
            }
        }
    });
}