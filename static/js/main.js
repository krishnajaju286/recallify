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

    // ========================================
    // 5. LANDING PAGE: Scroll Reveal Observer
    // ========================================
    const revealElements = document.querySelectorAll('.reveal-on-scroll');
    if (revealElements.length > 0) {
        const revealObserver = new IntersectionObserver(function(entries) {
            entries.forEach(function(entry) {
                if (entry.isIntersecting) {
                    entry.target.classList.add('revealed');
                    revealObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12 });

        revealElements.forEach(function(el) {
            revealObserver.observe(el);
        });
    }

    // ========================================
    // 6. LANDING PAGE: Gradient Scroll Phases
    // ========================================
    const landingBody = document.querySelector('.landing-body');
    if (landingBody) {
        window.addEventListener('scroll', function() {
            const scrollY = window.scrollY;
            const docHeight = document.documentElement.scrollHeight - window.innerHeight;
            const scrollPercent = docHeight > 0 ? (scrollY / docHeight) * 100 : 0;

            landingBody.classList.remove('scroll-phase-1', 'scroll-phase-2', 'scroll-phase-3', 'scroll-phase-4');
            if (scrollPercent < 25) {
                landingBody.classList.add('scroll-phase-1');
            } else if (scrollPercent < 50) {
                landingBody.classList.add('scroll-phase-2');
            } else if (scrollPercent < 75) {
                landingBody.classList.add('scroll-phase-3');
            } else {
                landingBody.classList.add('scroll-phase-4');
            }
        });
    }

    // ========================================
    // 7. LANDING PAGE: Active Nav Link on Scroll
    // ========================================
    const navLinks = document.querySelectorAll('.nav-link-custom');
    const sections = document.querySelectorAll('.landing-section, .hero-section');
    if (navLinks.length > 0 && sections.length > 0) {
        window.addEventListener('scroll', function() {
            let currentSection = '';
            sections.forEach(function(section) {
                const top = section.offsetTop - 120;
                if (window.scrollY >= top) {
                    currentSection = section.getAttribute('id');
                }
            });
            navLinks.forEach(function(link) {
                link.classList.remove('active-link');
                if (link.getAttribute('href') === '#' + currentSection) {
                    link.classList.add('active-link');
                }
            });
        });
    }

    // ========================================
    // 8. LANDING PAGE: Navbar Shrink on Scroll
    // ========================================
    const navbar = document.querySelector('.landing-navbar');
    if (navbar) {
        window.addEventListener('scroll', function() {
            if (window.scrollY > 60) {
                navbar.classList.add('scrolled');
            } else {
                navbar.classList.remove('scrolled');
            }
        });
    }

    // ========================================
    // 9. LANDING PAGE: Auto-Playing Demo Slideshow
    // ========================================
    const demoPlayer = document.getElementById('demoVideoPlayer');
    if (demoPlayer) {
        let demoSlideIndex = 1;
        let demoInterval = null;
        const totalSlides = 4;
        const slideDelay = 4000; // 4 seconds per slide

        function showDemoSlide(n) {
            for (let i = 1; i <= totalSlides; i++) {
                const slide = document.getElementById('demoSlide' + i);
                const dot = demoPlayer.querySelector('.indicator-dot[data-slide="' + i + '"]');
                if (slide) slide.style.display = 'none';
                if (dot) dot.style.background = '#555';
            }
            const activeSlide = document.getElementById('demoSlide' + n);
            const activeDot = demoPlayer.querySelector('.indicator-dot[data-slide="' + n + '"]');
            if (activeSlide) activeSlide.style.display = 'block';
            if (activeDot) activeDot.style.background = '#10b981';
        }

        function nextDemoSlide() {
            demoSlideIndex = (demoSlideIndex % totalSlides) + 1;
            showDemoSlide(demoSlideIndex);
        }

        function startDemoLoop() {
            if (demoInterval) clearInterval(demoInterval);
            demoInterval = setInterval(nextDemoSlide, slideDelay);
        }

        function stopDemoLoop() {
            if (demoInterval) clearInterval(demoInterval);
        }

        // Dot click handlers
        const dots = demoPlayer.querySelectorAll('.indicator-dot');
        dots.forEach(function(dot) {
            dot.addEventListener('click', function() {
                demoSlideIndex = parseInt(this.getAttribute('data-slide'));
                showDemoSlide(demoSlideIndex);
                startDemoLoop(); // restart timer
            });
        });

        // Auto-start when modal opens
        const videoModal = document.getElementById('videoModal');
        if (videoModal) {
            videoModal.addEventListener('shown.bs.modal', function() {
                demoSlideIndex = 1;
                showDemoSlide(1);
                startDemoLoop();
            });
            videoModal.addEventListener('hidden.bs.modal', function() {
                stopDemoLoop();
            });
        }
    }

    // ========================================
    // 10. LANDING PAGE: Legal Modal Tab Pre-Opener
    // ========================================
    const legalModal = document.getElementById('legalModal');
    if (legalModal) {
        legalModal.addEventListener('show.bs.modal', function(event) {
            const trigger = event.relatedTarget;
            if (trigger) {
                const tab = trigger.getAttribute('data-legal-tab');
                // Collapse all
                const collapseTerms = document.getElementById('landingCollapseTerms');
                const collapsePrivacy = document.getElementById('landingCollapsePrivacy');
                if (collapseTerms) collapseTerms.classList.remove('show');
                if (collapsePrivacy) collapsePrivacy.classList.remove('show');

                // Open the requested one
                setTimeout(function() {
                    if (tab === 'terms' && collapseTerms) {
                        new bootstrap.Collapse(collapseTerms, { toggle: true });
                    } else if (tab === 'privacy' && collapsePrivacy) {
                        new bootstrap.Collapse(collapsePrivacy, { toggle: true });
                    }
                }, 200);
            }
        });
    }
});
