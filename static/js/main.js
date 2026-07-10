document.addEventListener('DOMContentLoaded', function() {
    // 1. Alert auto-dismissal
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            // Fade out
            alert.style.transition = 'opacity 0.5s ease';
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.remove();
            }, 500);
        }, 4000);
    });

    // 2. Mobile sidebar toggle
    const toggleBtn = document.getElementById('sidebarToggle');
    const sidebar = document.querySelector('.app-sidebar');
    
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            sidebar.classList.toggle('show');
        });

        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(e) {
            if (window.innerWidth < 992) {
                if (!sidebar.contains(e.target) && e.target !== toggleBtn) {
                    sidebar.classList.remove('show');
                }
            }
        });
    }

    // 3. Theme Toggle Switcher
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        // Initialize icon on load
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        updateThemeIcon(themeToggle, currentTheme);
        
        themeToggle.addEventListener('click', function() {
            const activeTheme = document.documentElement.getAttribute('data-theme') || 'light';
            const newTheme = activeTheme === 'light' ? 'dark' : 'light';
            
            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(themeToggle, newTheme);
        });
    }
    
    function updateThemeIcon(btn, theme) {
        const icon = btn.querySelector('i');
        if (icon) {
            if (theme === 'dark') {
                icon.className = 'bi bi-sun';
            } else {
                icon.className = 'bi bi-moon-stars';
            }
        }
    }
    // 4. Idle Auto-Reload (Dashboard Only)
    const dashboardReloadBtn = document.getElementById('dashboardReloadBtn');
    if (dashboardReloadBtn) {
        let idleTimer;
        const idleLimit = 30000; // 30 seconds

        function resetIdleTimer() {
            clearTimeout(idleTimer);
            idleTimer = setTimeout(function() {
                window.location.reload();
            }, idleLimit);
        }

        // Add activity event listeners to reset the timer
        const events = ['mousemove', 'keypress', 'click', 'scroll', 'touchstart'];
        events.forEach(function(evt) {
            document.addEventListener(evt, resetIdleTimer, true);
        });

        // Initialize on load
        resetIdleTimer();
    }
});
