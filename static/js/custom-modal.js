/**
 * Custom Modal Implementation
 * This script creates a custom modal system that doesn't rely on Bootstrap's modal implementation
 * to avoid the flickering issues
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize our custom modal system
    initCustomModals();
});

function initCustomModals() {
    // Find all delete buttons that should trigger our custom modals
    // Target ALL buttons that could open modals for deletion, not just .btn-delete
    const deleteButtons = document.querySelectorAll('.btn-delete, button[data-bs-toggle="modal"], a[data-bs-toggle="modal"]');
    
    deleteButtons.forEach(button => {
        // Get the target modal id 
        const modalId = button.getAttribute('data-bs-target') || button.getAttribute('data-target');
        if (!modalId) return;
        
        // Skip if not a delete modal (check classes or text content)
        const isDeleteButton = 
            button.classList.contains('btn-delete') || 
            button.classList.contains('btn-danger') ||
            (button.textContent && button.textContent.toLowerCase().includes('delete')) ||
            (modalId.toLowerCase().includes('delete'));
            
        if (!isDeleteButton) return;
        
        // Remove the # from the id
        const modalIdWithoutHash = modalId.startsWith('#') ? modalId.substring(1) : modalId;
        
        // Find the original Bootstrap modal
        const originalModal = document.getElementById(modalIdWithoutHash);
        if (!originalModal) return;
        
        // Also check if modal is a delete confirmation
        const isDeleteModal = 
            originalModal.classList.contains('delete-confirmation-modal') ||
            (originalModal.querySelector('.modal-body') && 
             originalModal.querySelector('.modal-body').textContent.toLowerCase().includes('delete'));
             
        if (!isDeleteModal) return;
        
        // Hide the original modal completely by making it display:none immediately
        originalModal.style.display = 'none';
        
        // Create our custom modal content based on the original
        const customModalHTML = createCustomModalHTML(originalModal, modalIdWithoutHash);
        
        // Add event listener to the delete button to show our custom modal
        button.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Show the custom modal
            showCustomModal(customModalHTML, modalIdWithoutHash);
            
            return false;
        });
        
        // Remove bootstrap's data attributes to prevent it from trying to show the modal
        button.removeAttribute('data-bs-toggle');
        button.removeAttribute('data-bs-target');
        button.removeAttribute('data-target');
    });
}

function createCustomModalHTML(originalModal, modalId) {
    // Extract the title
    const titleElement = originalModal.querySelector('.modal-title');
    const title = titleElement ? titleElement.textContent : 'Confirm Action';
    
    // Extract the body content
    const bodyElement = originalModal.querySelector('.modal-body');
    const bodyContent = bodyElement ? bodyElement.innerHTML : '';
    
    // Extract the form details
    const formElement = originalModal.querySelector('form');
    
    // Create footer content with appropriate buttons
    let footerContent;
    
    if (formElement) {
        // Get form attributes
        const formAction = formElement ? formElement.getAttribute('action') : '';
        const csrfInput = formElement.querySelector('input[name="csrf_token"]');
        const csrfToken = csrfInput ? csrfInput.value : '';
        
        // Check if it's a standard deletion modal
        const deleteButton = formElement.querySelector('.btn-danger, .delete-confirm-btn');
        const deleteButtonText = deleteButton ? deleteButton.textContent.trim() : 'Delete';
        
        // Look for hidden inputs that should be preserved
        const hiddenInputs = formElement.querySelectorAll('input[type="hidden"]');
        let hiddenInputsHTML = '';
        
        hiddenInputs.forEach(input => {
            // Skip the challenge_action if we're going to add our own
            if (input.name === 'challenge_action') return;
            
            hiddenInputsHTML += `<input type="hidden" name="${input.name}" value="${input.value}">`;
        });
        
        // Check if we need challenge_action input
        const challengeActionExists = originalModal.textContent.toLowerCase().includes('challenge') && 
                                     originalModal.textContent.toLowerCase().includes('action');
        
        // Build the form with all necessary inputs
        const actionInputHTML = challengeActionExists ? 
            `<input type="hidden" name="challenge_action" id="customHiddenAction-${modalId}" value="delete">` : '';
        
        footerContent = `
            <button type="button" class="btn btn-secondary" onclick="closeCustomModal('${modalId}')">Cancel</button>
            <form action="${formAction}" method="POST" class="d-inline">
                <input type="hidden" name="csrf_token" value="${csrfToken}">
                ${hiddenInputsHTML}
                ${actionInputHTML}
                <button type="submit" class="btn btn-danger">${deleteButtonText}</button>
            </form>
        `;
    } else {
        // Simple confirm/cancel buttons if no form found
        footerContent = `
            <button type="button" class="btn btn-secondary" onclick="closeCustomModal('${modalId}')">Cancel</button>
            <button type="button" class="btn btn-danger" onclick="confirmCustomModal('${modalId}')">Delete</button>
        `;
    }
    
    // Build the HTML for our custom modal
    return `
        <div class="custom-modal-backdrop" id="backdrop-${modalId}"></div>
        <div class="custom-modal" id="custom-${modalId}">
            <div class="custom-modal-content">
                <div class="custom-modal-header">
                    <h5 class="custom-modal-title">${title}</h5>
                    <button type="button" class="custom-close-button" onclick="closeCustomModal('${modalId}')">&times;</button>
                </div>
                <div class="custom-modal-body">
                    ${bodyContent}
                </div>
                <div class="custom-modal-footer">
                    ${footerContent}
                </div>
            </div>
        </div>
    `;
}

function showCustomModal(htmlContent, modalId) {
    // Create a container for our custom modal
    const container = document.createElement('div');
    container.id = `custom-modal-container-${modalId}`;
    container.innerHTML = htmlContent;
    
    // Safety check - make sure document.body exists before appending
    if (document.body) {
        document.body.appendChild(container);
        
        // Prevent scrolling of the body
        document.body.style.overflow = 'hidden';
    } else {
        console.error('Document body not available for modal container append');
        return; // Exit early if body not available
    }
    
    // Add the custom modal styles if they don't exist yet
    if (!document.getElementById('custom-modal-styles')) {
        addCustomModalStyles();
    }
    
    // Add event listeners for radio buttons in the modal
    setTimeout(() => {
        setupCustomModalRadios(modalId);
    }, 100);
}

function closeCustomModal(modalId) {
    // Remove the custom modal
    const container = document.getElementById(`custom-modal-container-${modalId}`);
    if (container && document.body) {
        try {
            document.body.removeChild(container);
            // Re-enable scrolling
            document.body.style.overflow = '';
        } catch (error) {
            console.error('Error removing modal container:', error);
        }
    }
}

function confirmCustomModal(modalId) {
    // Handle the confirm action for modals without forms
    // This simulates a click on the original modal's delete button
    
    // First close our custom modal
    closeCustomModal(modalId);
    
    // Find the original modal
    const originalModal = document.getElementById(modalId);
    if (!originalModal) return;
    
    // Find the original delete button and click it
    const originalDeleteButton = originalModal.querySelector('.btn-danger, .delete-confirm-btn');
    if (originalDeleteButton) {
        originalDeleteButton.click();
    } else {
        // If we can't find a button, try to submit any form in the modal
        const form = originalModal.querySelector('form');
        if (form) {
            form.submit();
        }
    }
}

function setupCustomModalRadios(modalId) {
    const customModal = document.getElementById(`custom-${modalId}`);
    if (!customModal) return;
    
    const radioButtons = customModal.querySelectorAll('input[type="radio"]');
    const hiddenInput = document.getElementById(`customHiddenAction-${modalId}`);
    
    radioButtons.forEach(radio => {
        // Make sure at least one is checked
        if (radio.getAttribute('checked')) {
            radio.checked = true;
        }
        
        radio.addEventListener('change', function() {
            if (hiddenInput) {
                hiddenInput.value = this.value;
            }
        });
    });
}

function addCustomModalStyles() {
    // Safety check to make sure document.head exists
    if (!document.head) {
        console.error('Document head not available for style append');
        return;
    }
    
    const styleTag = document.createElement('style');
    styleTag.id = 'custom-modal-styles';
    styleTag.textContent = `
        /* Custom Modal Styles */
        .custom-modal-backdrop {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.7);
            z-index: 2000;
        }
        
        .custom-modal {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            width: 90%;
            max-width: 500px;
            z-index: 2001;
            border-radius: 6px;
            overflow: hidden;
        }
        
        .custom-modal-content {
            background-color: #1e1e2e;
            width: 100%;
            border-radius: 6px;
            box-shadow: 0 0 30px rgba(0, 0, 0, 0.5);
        }
        
        .custom-modal-header {
            padding: 1rem;
            border-bottom: 1px solid #2c2c3a;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .custom-modal-title {
            margin: 0;
            color: white;
        }
        
        .custom-close-button {
            background: none;
            border: none;
            color: white;
            font-size: 1.5rem;
            cursor: pointer;
        }
        
        .custom-modal-body {
            padding: 1rem;
            color: white;
        }
        
        .custom-modal-footer {
            padding: 1rem;
            border-top: 1px solid #2c2c3a;
            display: flex;
            justify-content: flex-end;
            gap: 0.5rem;
        }
        
        /* Modal Form Controls */
        .custom-modal-body .form-check {
            padding: 0.75rem;
            margin-bottom: 0.5rem;
            background-color: #13131f;
            border: 1px solid #2c2c3a;
            border-radius: 4px;
        }
    `;
    
    try {
        document.head.appendChild(styleTag);
    } catch (error) {
        console.error('Error adding modal styles:', error);
    }
}