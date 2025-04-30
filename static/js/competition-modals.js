/**
 * Special fixes for competition management modals
 */
document.addEventListener('DOMContentLoaded', function() {
    // Fix competition delete modals
    fixCompetitionDeleteModals();
});

/**
 * Fix delete modals in competition management
 */
function fixCompetitionDeleteModals() {
    // Find all delete buttons
    const deleteButtons = document.querySelectorAll('.btn-delete');
    
    deleteButtons.forEach(button => {
        // Make the delete button more robust
        button.style.position = 'relative';
        button.style.zIndex = '5';
        
        // Get the modal from the button's data-bs-target
        const modalId = button.getAttribute('data-bs-target');
        if (!modalId) return;
        
        const modal = document.querySelector(modalId);
        if (!modal) return;
        
        // Add static backdrop to keep modal open when clicking outside
        modal.setAttribute('data-bs-backdrop', 'static');
        modal.setAttribute('data-bs-keyboard', 'false');
        
        // Add custom class for styling
        modal.classList.add('delete-confirmation-modal');
        
        // Fix radio buttons
        const radioButtons = modal.querySelectorAll('input[type="radio"]');
        
        // Make sure at least one is checked
        if (radioButtons.length > 0 && !Array.from(radioButtons).some(r => r.checked)) {
            radioButtons[0].checked = true;
        }
        
        // Find the form to submit the selected radio
        const form = modal.querySelector('form');
        if (!form) return;
        
        // Check if we need to add a hidden input
        let hiddenInput = form.querySelector('input[name="challenge_action"]');
        if (!hiddenInput) {
            hiddenInput = document.createElement('input');
            hiddenInput.type = 'hidden';
            hiddenInput.name = 'challenge_action';
            form.appendChild(hiddenInput);
        }
        
        // Set initial value
        const checkedRadio = Array.from(radioButtons).find(r => r.checked);
        if (checkedRadio) {
            hiddenInput.value = checkedRadio.value;
        }
        
        // Update hidden input when radio changes
        radioButtons.forEach(radio => {
            radio.addEventListener('change', function() {
                hiddenInput.value = this.value;
            });
        });
        
        // Make sure delete button has high z-index
        const deleteButton = form.querySelector('button[type="submit"]');
        if (deleteButton) {
            deleteButton.classList.add('delete-confirm-btn');
            deleteButton.style.position = 'relative';
            deleteButton.style.zIndex = '10';
        }
    });
}