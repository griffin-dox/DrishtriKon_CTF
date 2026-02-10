/**
 * App Configuration and Module Loader
 * Manages which JavaScript modules to load based on page type
 */

window.CTFAppConfig = {
    // Module loading configuration
    modules: {
        core: {
            file: 'app-core.js',
            pages: ['*'], // Load on all pages
            required: true
        },
        forms: {
            file: 'app-forms.js',
            pages: ['login', 'contact', 'challenges', 'auth', 'admin'],
            selectors: ['form', '.flag-form', '#loginForm', '#contactForm']
        },
        admin: {
            file: 'app-admin.js',
            pages: ['admin'],
            selectors: ['.admin-page', 'body[data-page="admin"]'],
            pathPrefix: '/admin'
        },
        charts: {
            file: 'charts.js',
            pages: ['admin', 'dashboard'],
            selectors: ['.chart-container', '[data-chart]']
        },
        ads: {
            file: 'ads.js',
            pages: ['index', 'home'],
            selectors: ['.ad-container', '.adsbygoogle']
        }
    },
    
    // Determine current page context
    getCurrentPageType: function() {
        const path = window.location.pathname;
        
        if (path.startsWith('/admin')) return 'admin';
        if (path === '/' || path === '/index') return 'home';
        if (path.includes('/auth/') || path.includes('/login')) return 'auth';
        if (path.includes('/challenges/')) return 'challenges';
        if (path.includes('/contact')) return 'contact';
        if (path.includes('/competitions/')) return 'competitions';
        
        return 'general';
    },
    
    // Check if page needs a specific module
    shouldLoadModule: function(moduleConfig) {
        const pageType = this.getCurrentPageType();
        const path = window.location.pathname;
        
        // Always load required modules
        if (moduleConfig.required) return true;
        
        // Check by page type
        if (moduleConfig.pages && moduleConfig.pages.includes('*')) return true;
        if (moduleConfig.pages && moduleConfig.pages.includes(pageType)) return true;
        
        // Check by path prefix
        if (moduleConfig.pathPrefix && path.startsWith(moduleConfig.pathPrefix)) return true;
        
        // Check by selector presence
        if (moduleConfig.selectors) {
            return moduleConfig.selectors.some(selector => 
                document.querySelector(selector) !== null
            );
        }
        
        return false;
    },
    
    // Load modules dynamically
    loadModules: function() {
        const basePath = '/static/js/';
        
        Object.entries(this.modules).forEach(([name, config]) => {
            if (this.shouldLoadModule(config)) {
                this.loadScript(basePath + config.file, name);
            }
        });
    },
    
    // Load a script dynamically
    loadScript: function(src, moduleName) {
        // Don't load if already loaded
        if (document.querySelector(`script[src="${src}"]`)) {
            return;
        }
        
        const script = document.createElement('script');
        script.src = src;
        script.async = true;
        script.setAttribute('data-module', moduleName);
        
        script.onload = () => {
            console.log(`✓ Module loaded: ${moduleName}`);
        };
        
        script.onerror = () => {
            console.warn(`✗ Failed to load module: ${moduleName}`);
        };
        
        document.head.appendChild(script);
    }
};

// Initialize module loading as early as possible
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        // Set reCAPTCHA site key if available in meta or global
        if (!window.RECAPTCHA_SITE_KEY) {
            const metaKey = document.querySelector('meta[name="recaptcha-site-key"]');
            if (metaKey) {
                window.RECAPTCHA_SITE_KEY = metaKey.getAttribute('content');
            }
        }
        
        CTFAppConfig.loadModules();
    });
} else {
    CTFAppConfig.loadModules();
}
