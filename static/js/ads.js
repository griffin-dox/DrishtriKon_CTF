/**
 * Advanced Ad Management for CTF platform
 * Supporting both Google Ads and custom uploaded images
 * Terminal-themed ad containers with CTF styling
 */

// Initialize ads when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
  // Keep track of initialized ad units to prevent duplicate initialization
  const initializedAds = new Set();
  
  // This function will be called when Google Ads library is loaded
  window.initAds = function() {
    // Initialize ad slots once the Google Ads API is ready
    if (window.adsbygoogle) {
      console.log('Google Ads initialized');
      
      // Hide sidebar ads on all pages except homepage
      const currentPath = window.location.pathname;
      const isHomePage = currentPath === '/' || currentPath === '/index';
      
      // Hide all sidebar ads
      document.querySelectorAll('.ad-container-left, .ad-container-right, .ad-sidebar').forEach(function(container) {
        // Only show sidebar ads on homepage
        if (!isHomePage) {
          container.style.display = 'none';
        }
      });
      
      // Hide all horizontal ads except on homepage
      if (!isHomePage) {
        document.querySelectorAll('.ad-container.ad-banner').forEach(function(container) {
          // Exclude the home-specific ad
          if (!container.classList.contains('home-ad')) {
            container.style.display = 'none';
          }
        });
      }
      
      // Initialize each ad unit on the page (only for visible containers)
      document.querySelectorAll('.adsbygoogle').forEach(function(ad) {
        // Generate a unique identifier for this ad unit
        const adId = ad.dataset.adSlot || Math.random().toString(36).substring(2, 15);
        
        // Only initialize visible Google Ads that haven't been initialized yet
        const container = ad.closest('.ad-container, .ad-container-left, .ad-container-right');
        if (container && 
            getComputedStyle(container).display !== 'none' &&
            !container.classList.contains('custom-ad-active') &&
            !initializedAds.has(adId)) {
          try {
            // Mark this ad as initialized
            initializedAds.add(adId);
            
            // Set the identifier as a data attribute
            ad.dataset.adSlot = adId;
            
            // Push ad configuration
            (adsbygoogle = window.adsbygoogle || []).push({});
          } catch (e) {
            console.error('Error initializing ad unit:', e);
          }
        }
      });
    }
  };

  // For when Google Ads script loads before our initialization
  if (window.adsbygoogle) {
    initAds();
  }

  // Apply CTF-themed styling to ad containers
  const styleAdContainers = function() {
    // Target all ad containers (horizontal and vertical)
    document.querySelectorAll('.ad-container, .ad-container-left, .ad-container-right').forEach(function(container) {
      container.classList.add('ctf-ad-styled');
      
      // Add terminal-like decoration if not already present
      if (!container.querySelector('.terminal-dots')) {
        // Add a small terminal-like decoration to each ad container
        const terminalDecoration = document.createElement('div');
        terminalDecoration.className = 'terminal-dots';
        terminalDecoration.innerHTML = '<span class="dot dot-red"></span><span class="dot dot-yellow"></span><span class="dot dot-green"></span>';
        
        // Insert at the beginning of each ad header
        const adHeader = container.querySelector('.ad-header');
        if (adHeader && !adHeader.querySelector('.terminal-dots')) {
          adHeader.prepend(terminalDecoration);
        }
      }
      
      // Get the location ID from data attribute
      const locationId = container.dataset.location;
      
      // If we have a location ID, fetch the custom ad or use Google Ads
      if (locationId) {
        fetchAdContent(container, locationId);
      }
    });
  };
  
  // Fetch custom ad content from API or show Google Ads
  const fetchAdContent = function(container, locationId) {
    // Check current path to decide whether to show this ad
    const currentPath = window.location.pathname;
    const isHomePage = currentPath === '/' || currentPath === '/index';
    
    // For sidebar ads: only show on homepage
    if ((container.classList.contains('ad-container-left') || 
         container.classList.contains('ad-container-right') ||
         container.classList.contains('ad-sidebar')) &&
        !isHomePage) {
      container.style.display = 'none';
      return; // Exit early, don't initialize this ad
    }
    
    // For horizontal ads: only show on homepage
    if (container.classList.contains('ad-banner') && 
        !container.classList.contains('home-ad') && 
        !isHomePage) {
      container.style.display = 'none';
      return; // Exit early, don't initialize this ad
    }
    
    // For non-homepage horizontal ads
    if (container.classList.contains('ad-banner') && 
        !container.classList.contains('home-ad') && 
        isHomePage) {
      container.style.display = 'none';
      return; // Exit early, don't initialize this ad
    }
    
    // For now, use Google Ads directly to avoid API errors and ensure ads are displayed
    // This is a temporary fix until the API endpoint issue is resolved
    
    // Use Google Ads
    const googleAd = container.querySelector('.adsbygoogle');
    if (googleAd) {
      googleAd.style.display = 'block';
    }
    
    // Remove any custom ad
    const customAd = container.querySelector('.custom-ad');
    if (customAd) {
      customAd.remove();
    }
    
    // For testing purposes only, comment out the fetch call
    /*
    fetch(`/api/get-ad/${locationId.toLowerCase()}`)
      .then(response => response.json())
      .then(data => {
        // Check if we have an ad to display (either Google or custom)
        const hasAd = data.use_google_ads || data.ad;
        
        // For fixed position ad containers, show/hide the entire container
        if (container.classList.contains('ad-container-left') || 
            container.classList.contains('ad-container-right')) {
          // Only display the container if we have an ad
          container.style.display = hasAd ? 'block' : 'none';
        }
        
        // If using Google Ads, activate Google Ads
        if (data.use_google_ads) {
          // Make sure the adsbygoogle div is visible
          const googleAd = container.querySelector('.adsbygoogle');
          if (googleAd) {
            googleAd.style.display = 'block';
            
            // We don't need to push an ad here anymore as it's handled in the initAds function
            // This prevents duplicate initialization errors
          }
          
          // Remove any custom ad
          const customAd = container.querySelector('.custom-ad');
          if (customAd) {
            customAd.remove();
          }
          
          container.classList.remove('custom-ad-active');
        } 
        // If using custom ad, display it
        else if (data.ad) {
          // Hide Google Ads
          const googleAd = container.querySelector('.adsbygoogle');
          if (googleAd) {
            googleAd.style.display = 'none';
          }
          
          // Remove any existing custom ad
          const existingCustomAd = container.querySelector('.custom-ad');
          if (existingCustomAd) {
            existingCustomAd.remove();
          }
          
          // Create custom ad element
          const customAd = document.createElement('div');
          customAd.className = 'custom-ad';
          
          // Create link if URL provided
          if (data.ad.link_url) {
            const adLink = document.createElement('a');
            adLink.href = data.ad.link_url;
            adLink.target = '_blank';
            adLink.className = 'custom-ad-link';
            
            const img = document.createElement('img');
            img.src = '/' + data.ad.image_path;
            img.alt = data.ad.title;
            img.className = 'img-fluid custom-ad-image';
            
            adLink.appendChild(img);
            customAd.appendChild(adLink);
          } else {
            // Just the image without a link
            const img = document.createElement('img');
            img.src = '/' + data.ad.image_path;
            img.alt = data.ad.title;
            img.className = 'img-fluid custom-ad-image';
            customAd.appendChild(img);
          }
          
          // Add the custom ad to the container
          container.appendChild(customAd);
          container.classList.add('custom-ad-active');
        } else {
          // If we don't have any ad to display, hide the container for horizontal ads
          // Vertical ads are already handled above
          if (!container.classList.contains('ad-container-left') && 
              !container.classList.contains('ad-container-right')) {
            container.style.display = 'none';
          }
        }
      })
      .catch(error => {
        console.error('Error fetching ad content:', error);
        
        // Hide the container if there was an error
        if (container.classList.contains('ad-container-left') || 
            container.classList.contains('ad-container-right')) {
          container.style.display = 'none';
        } else {
          container.style.display = 'none';
        }
      });
    */
  };
  
  // Style ad containers when page loads
  styleAdContainers();
  
  // Add special CSS for ad containers
  const addAdStyles = function() {
    try {
      // Safety check for existing element
      if (document.getElementById('ctf-ad-styles')) {
        return; // Styles already added
      }
      
      // Safety check to ensure document.head exists
      if (!document.head) {
        console.error('Document head not available yet');
        return;
      }
      
      const style = document.createElement('style');
      style.id = 'ctf-ad-styles';
      style.textContent = `
        .custom-ad {
          width: 100%;
          display: flex;
          justify-content: center;
          align-items: center;
        }
        
        .custom-ad-image {
          max-width: 100%;
          height: auto;
          border: 1px solid var(--primary-color);
          transition: all 0.3s ease;
        }
        
        .custom-ad-link:hover .custom-ad-image {
          box-shadow: 0 0 15px var(--primary-color);
        }
        
        .ad-container.custom-ad-active .adsbygoogle,
        .ad-container-left.custom-ad-active .adsbygoogle,
        .ad-container-right.custom-ad-active .adsbygoogle {
          display: none !important;
        }
        
        /* Terminal decoration style */
        .terminal-dots {
          display: flex;
          gap: 5px;
          margin-right: 8px;
        }
        
        .dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        
        .dot-red {
          background-color: #ff5f56;
        }
        
        .dot-yellow {
          background-color: #ffbd2e;
        }
        
        .dot-green {
          background-color: #27c93f;
        }
      `;
      document.head.appendChild(style);
    } catch (error) {
      console.error('Error adding ad styles:', error);
    }
  };
  
  // Add terminal-like decoration styles
  // Make sure the document is fully loaded before adding styles
  if (document.readyState === 'complete' || document.readyState === 'interactive') {
    addAdStyles();
  } else {
    window.addEventListener('DOMContentLoaded', addAdStyles);
  }
});