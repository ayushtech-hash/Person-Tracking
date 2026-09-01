(function () {
    const menu = document.getElementById("account-menu");
    const toggle = document.getElementById("account-menu-toggle");
    const profileButton = document.getElementById("account-profile-toggle");
    const profilePanel = document.getElementById("account-profile-panel");
    const logoutButton = document.getElementById("account-logout-button");

    if (!menu || !toggle) return;

    function setMenuOpen(isOpen) {
        menu.classList.toggle("is-open", isOpen);
        toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    }

    function setProfileOpen(isOpen) {
        if (!profilePanel) return;
        profilePanel.hidden = !isOpen;
        if (profileButton) {
            profileButton.setAttribute("aria-expanded", isOpen ? "true" : "false");
        }
    }

    toggle.addEventListener("click", function () {
        setMenuOpen(!menu.classList.contains("is-open"));
    });

    document.addEventListener("click", function (event) {
        if (!menu.contains(event.target)) {
            setMenuOpen(false);
            setProfileOpen(false);
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
            setMenuOpen(false);
            setProfileOpen(false);
            toggle.focus();
        }
    });

    if (profileButton) {
        profileButton.addEventListener("click", function () {
            setProfileOpen(profilePanel ? profilePanel.hidden : true);
        });
    }

    if (logoutButton) {
        logoutButton.addEventListener("click", async function () {
            logoutButton.disabled = true;
            logoutButton.textContent = "Logging out...";

            try {
                await fetch("/api/auth/logout/", {
                    method: "POST",
                    credentials: "include",
                });
            } finally {
                window.location.href = "/login/";
            }
        });
    }
})();
