// Scripts
(function($) {


    // Year
    document.getElementById("current-year").innerHTML = new Date().getFullYear();

    "use strict";


    // Toggle
document.addEventListener("DOMContentLoaded", function() {
    const sidebar = document.getElementById("sidebar");
    const mainContent = document.getElementById("main-content");
    const toggleBtn = document.querySelector(".toggle-sidebar-btn");

    // Check if elements exist
    if (sidebar && mainContent && toggleBtn) {
        // Define the toggleSidebar function
        function toggleSidebar() {
            sidebar.classList.toggle("collapsed");
            mainContent.classList.toggle("sidebar-collapsed");
        }

        // Add event listener to the toggle button
        toggleBtn.addEventListener("click", toggleSidebar);

        // Automatically collapse sidebar on smaller screens
        function checkScreenWidth() {
            if (window.innerWidth < 768) {
                sidebar.classList.add("collapsed");
                mainContent.classList.add("sidebar-collapsed");
            } else {
                sidebar.classList.remove("collapsed");
                mainContent.classList.remove("sidebar-collapsed");
            }
        }

        // Initial check and listen for resize events
        checkScreenWidth();
        window.addEventListener("resize", checkScreenWidth);
    } else {
        console.error("Sidebar, main content, or toggle button is missing.");
    }
});


 
    // Scroll to top on button click
      $(document).ready(function () {
        $(this).scrollTop(0);
        $('#toTop').on('click', function () {
          $('body,html').animate({
            scrollTop: 0
          }, 500);
        });
      });


    // tooltip 
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]')
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl))



    // Passivelisteners
    jQuery.event.special.touchstart = {
        setup: function(_, ns, handle) {
            this.addEventListener("touchstart", handle, {
                passive: !ns.includes("noPreventDefault")
            });
        }
    };
    jQuery.event.special.touchmove = {
        setup: function(_, ns, handle) {
            this.addEventListener("touchmove", handle, {
                passive: !ns.includes("noPreventDefault")
            });
        }
    };
    jQuery.event.special.wheel = {
        setup: function(_, ns, handle) {
            this.addEventListener("wheel", handle, {
                passive: true
            });
        }
    };
    jQuery.event.special.mousewheel = {
        setup: function(_, ns, handle) {
            this.addEventListener("mousewheel", handle, {
                passive: true
            });
        }
    };


})(window.jQuery);

// End Script