/**
 * Admin-specific functionality
 * Extends the core CTF app with admin panel features
 */

// Extend CTF App for admin functionality
CTFApp.Admin = {
    // Enhanced table management for admin panels
    initTable: function(tableSelector = '.table') {
        const tables = document.querySelectorAll(tableSelector);
        
        tables.forEach(table => {
            // Optimize rendering
            table.classList.add('no-flicker');
            
            // Optimize rows
            table.querySelectorAll('tr').forEach(row => {
                row.classList.add('no-animation');
                
                // Prevent hover effects during modal operations
                row.addEventListener('mouseenter', function(e) {
                    if (document.body.classList.contains('modal-open')) {
                        e.preventDefault();
                        e.stopPropagation();
                        return false;
                    }
                }, true);
            });
        });
    },
    
    // Bulk actions for admin tables
    initBulkActions: function() {
        const selectAllCheckbox = document.querySelector('#selectAll');
        const itemCheckboxes = document.querySelectorAll('.item-checkbox');
        const bulkActionBtn = document.querySelector('#bulkActionBtn');
        
        if (selectAllCheckbox && itemCheckboxes.length > 0) {
            selectAllCheckbox.addEventListener('change', function() {
                itemCheckboxes.forEach(checkbox => {
                    checkbox.checked = this.checked;
                });
                this.updateBulkActionState();
            }.bind(this));
            
            itemCheckboxes.forEach(checkbox => {
                checkbox.addEventListener('change', this.updateBulkActionState.bind(this));
            });
        }
    },
    
    updateBulkActionState: function() {
        const checkedItems = document.querySelectorAll('.item-checkbox:checked');
        const bulkActionBtn = document.querySelector('#bulkActionBtn');
        
        if (bulkActionBtn) {
            bulkActionBtn.disabled = checkedItems.length === 0;
            bulkActionBtn.textContent = `Actions (${checkedItems.length} selected)`;
        }
    },
    
    // Enhanced user management
    initUserManagement: function() {
        // Handle user role changes
        document.querySelectorAll('.role-select').forEach(select => {
            select.addEventListener('change', function() {
                const userId = this.getAttribute('data-user-id');
                const newRole = this.value;
                
                CTFApp.Modal.confirm({
                    title: 'Change User Role',
                    message: `Change user role to "${newRole}"?`,
                    confirmText: 'Change Role',
                    confirmClass: 'btn-warning',
                    onConfirm: () => {
                        this.updateUserRole(userId, newRole);
                    }
                });
            }.bind(this));
        });
        
        // Handle user status toggles
        document.querySelectorAll('.status-toggle').forEach(toggle => {
            toggle.addEventListener('change', function() {
                const userId = this.getAttribute('data-user-id');
                const isActive = this.checked;
                
                this.updateUserStatus(userId, isActive);
            }.bind(this));
        });
    },
    
    updateUserRole: function(userId, role) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/admin/users/' + userId + '/role';
        
        // Add CSRF token
        CTFApp.Utils.csrfToken.injectToForm(form);
        
        // Add role input
        const roleInput = document.createElement('input');
        roleInput.type = 'hidden';
        roleInput.name = 'role';
        roleInput.value = role;
        form.appendChild(roleInput);
        
        document.body.appendChild(form);
        form.submit();
    },
    
    updateUserStatus: function(userId, isActive) {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/admin/users/' + userId + '/status';
        
        // Add CSRF token
        CTFApp.Utils.csrfToken.injectToForm(form);
        
        // Add status input
        const statusInput = document.createElement('input');
        statusInput.type = 'hidden';
        statusInput.name = 'is_active';
        statusInput.value = isActive ? '1' : '0';
        form.appendChild(statusInput);
        
        document.body.appendChild(form);
        form.submit();
    }
};

// Auto-initialize admin features
document.addEventListener('DOMContentLoaded', function() {
    // Only run on admin pages
    if (document.body.classList.contains('admin-page') || 
        window.location.pathname.startsWith('/admin')) {
        
        CTFApp.Admin.initTable();
        CTFApp.Admin.initBulkActions();
        CTFApp.Admin.initUserManagement();
        
        // Prevent interference during modal operations
        document.addEventListener('click', function(event) {
            if (document.body.classList.contains('modal-open')) {
                const modalContent = event.target.closest('.modal-content');
                const isModalControl = event.target.closest('.btn') || 
                                      event.target.closest('.modal-dialog');
                
                if (!modalContent && !isModalControl) {
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
    }
});
