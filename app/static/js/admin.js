// JavaScript for Admin Dashboard with enhanced stability for admin users

document.addEventListener('DOMContentLoaded', function() {
    // Directly add CSRF tokens to all forms to ensure they're present
    document.querySelectorAll('form').forEach(function(form) {
        const metaToken = document.querySelector('meta[name="csrf-token"]');
        if (metaToken && !form.querySelector('input[name="csrf_token"]')) {
            const csrfInput = document.createElement('input');
            csrfInput.type = 'hidden';
            csrfInput.name = 'csrf_token';
            csrfInput.value = metaToken.getAttribute('content');
            form.appendChild(csrfInput);
        }
    });

    // Global click handler to prevent unwanted click events during modal operation
    document.addEventListener('click', function(event) {
        if (document.body.classList.contains('modal-open')) {
            const modalContent = event.target.closest('.modal-content');
            const isModalBtn = event.target.closest('.btn-delete') || 
                              event.target.closest('.modal-cancel-btn') || 
                              event.target.closest('.modal-dialog');
            
            // If click is outside modal content and not on a control button, prevent it
            if (!modalContent && !isModalBtn) {
                event.preventDefault();
                event.stopPropagation();
                return false;
            }
        }
    }, true);

    // Prevent text selection during modal operations
    document.body.addEventListener('selectstart', function(event) {
        if (document.body.classList.contains('modal-open')) {
            const isFormInput = event.target.tagName === 'INPUT' || 
                               event.target.tagName === 'TEXTAREA';
            if (!isFormInput) {
                event.preventDefault();
                return false;
            }
        }
    }, true);

    // Custom implementation for modals to completely avoid Bootstrap animation issues
    function openStableModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;

        // Create a completely new backdrop for this specific modal
        const uniqueBackdropId = 'backdrop-' + modalId;
        let backdrop = document.getElementById(uniqueBackdropId);
        if (!backdrop) {
            backdrop = document.createElement('div');
            backdrop.id = uniqueBackdropId;
            backdrop.className = 'modal-backdrop show';
            backdrop.style.zIndex = '1050';
            backdrop.style.opacity = '0.85';
            document.body.appendChild(backdrop);
        }

        // Disable all animations for performance
        document.body.classList.add('modal-animating');
        
        // Display modal with no transition
        modal.style.display = 'block';
        modal.style.paddingRight = '0';
        modal.classList.add('show');
        document.body.classList.add('modal-open');
        document.body.style.overflow = 'hidden';
        
        // Focus handle for better keyboard access
        setTimeout(function() {
            const cancelBtn = modal.querySelector('.modal-cancel-btn');
            if (cancelBtn) cancelBtn.focus();
            
            // Ensure all forms have CSRF token
            const form = modal.querySelector('form');
            if (form) {
                const metaToken = document.querySelector('meta[name="csrf-token"]');
                const csrfInput = form.querySelector('input[name="csrf_token"]');
                
                if (metaToken && (!csrfInput || !csrfInput.value)) {
                    // Remove existing token if invalid
                    if (csrfInput) {
                        form.removeChild(csrfInput);
                    }
                    
                    // Add fresh token
                    const newCsrfInput = document.createElement('input');
                    newCsrfInput.type = 'hidden';
                    newCsrfInput.name = 'csrf_token';
                    newCsrfInput.value = metaToken.getAttribute('content');
                    form.appendChild(newCsrfInput);
                }
            }
            
            document.body.classList.remove('modal-animating');
        }, 50);
        
        return modal;
    }

    // Function to close modal cleanly
    function closeStableModal(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        
        // Remove backdrop
        const backdrop = document.getElementById('backdrop-' + modalId);
        if (backdrop) {
            document.body.removeChild(backdrop);
        }
        
        // Hide modal
        modal.style.display = 'none';
        modal.classList.remove('show');
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
    }

    // Register cancel buttons inside modals
    document.querySelectorAll('.modal-cancel-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const modal = this.closest('.modal');
            if (modal) {
                closeStableModal(modal.id);
            }
        });
    });

    // Delete buttons with enhanced stability
    document.querySelectorAll('.btn-delete').forEach(function(deleteBtn) {
        // Remove any existing handlers by replacing element
        const newDeleteBtn = deleteBtn.cloneNode(true);
        if (deleteBtn.parentNode) {
            deleteBtn.parentNode.replaceChild(newDeleteBtn, deleteBtn);
        }
        
        // Add our custom stable handler
        newDeleteBtn.addEventListener('click', function(event) {
            event.preventDefault();
            event.stopPropagation();
            
            // Get modal ID from data attribute
            const targetId = this.getAttribute('data-target');
            if (targetId) {
                const modalId = targetId.substring(1); // Remove # prefix
                openStableModal(modalId);
            }
        });
    });

    // Process all forms with CSRF token injection
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function(event) {
            const csrfInput = this.querySelector('input[name="csrf_token"]');
            const metaToken = document.querySelector('meta[name="csrf-token"]');
            
            // If the form doesn't have a CSRF token but one is available in meta
            if (metaToken && (!csrfInput || !csrfInput.value)) {
                event.preventDefault();
                
                // Create or update CSRF input
                let newCsrfInput = csrfInput;
                if (!newCsrfInput) {
                    newCsrfInput = document.createElement('input');
                    newCsrfInput.type = 'hidden';
                    newCsrfInput.name = 'csrf_token';
                    this.appendChild(newCsrfInput);
                }
                
                // Set token value and resubmit
                newCsrfInput.value = metaToken.getAttribute('content');
                setTimeout(() => {
                    this.submit();
                }, 10);
            }
        });
    });

    // Optimize table rendering
    const userTable = document.querySelector('.table');
    if (userTable) {
        userTable.classList.add('no-flicker');
        
        // Optimize table row rendering
        userTable.querySelectorAll('tr').forEach(function(row) {
            row.classList.add('no-animation');
            
            // Prevent hover effects completely
            row.addEventListener('mouseenter', function(e) {
                e.preventDefault();
                if (document.body.classList.contains('modal-open')) {
                    e.stopPropagation();
                    return false;
                }
            }, true);
        });
    }
});