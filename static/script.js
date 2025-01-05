const dashboardButton = document.getElementById("dashboardAccess");
        const loginPopup = document.getElementById("loginPopup");
        const closePopupButton = document.getElementById("closePopup");

        // Show login popup when dashboard is accessed
        dashboardButton.addEventListener("click", () => {
            loginPopup.style.display = "block";
        });

        // Close login popup
        closePopupButton.addEventListener("click", () => {
            loginPopup.style.display = "none";
        });

        // Handle login form submission
        document.getElementById("loginForm").addEventListener("submit", async (e) => {
            e.preventDefault();
            const formData = new FormData(e.target);

            const response = await fetch("/login", {
                method: "POST",
                body: formData
            });

            if (response.ok) {
                loginPopup.style.display = "none";
                window.location.href = "/dashboard"; // Redirect to dashboard on successful login
            } else {
                alert("Invalid credentials. Please try again.");
            }
        });