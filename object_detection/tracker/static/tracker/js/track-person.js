(function () {
    const trackPersonBtn =
        document.getElementById(
            "lightbox-track-person"
        );

    if (!trackPersonBtn) {
        return;
    }

    trackPersonBtn.style.display = "none";


    // ---------------------------------------------------------
    // Track Person availability
    // ---------------------------------------------------------

    window.setTrackPersonAvailable =
        function (available) {

            trackPersonBtn.style.display =
                available
                    ? "inline-flex"
                    : "none";
        };

    // ---------------------------------------------------------
    // Track Person
    // ---------------------------------------------------------

    trackPersonBtn.addEventListener(
        "click",
        async function () {

            const trackData =
                window.getLightboxTrackData
                    ? window.getLightboxTrackData()
                    : null;

            if (
                !trackData ||
                !trackData.trackId ||
                !trackData.reportId
            ) {

                alert(
                    "Track ID or Report ID is missing."
                );

                return;
            }

            trackPersonBtn.disabled =
                true;

            trackPersonBtn.textContent =
                "Generating...";


            try {

                const formData =
                    new FormData();


                formData.append(
                    "track_id",
                    trackData.trackId
                );

                formData.append(
                    "report_id",
                    trackData.reportId
                );

                const config =
                    document.getElementById(
                        "app-config"
                    );

                const csrfToken =
                    document.querySelector(
                        "[name=csrfmiddlewaretoken]"
                    );

                const response =
                    await fetch(
                        config.dataset
                            .separateVideoUrl,
                        {
                            method: "POST",

                            headers: {
                                "X-CSRFToken":
                                    csrfToken
                                        ? csrfToken.value
                                        : "",

                                "X-Requested-With":
                                    "XMLHttpRequest"
                            },

                            body: formData
                        }
                    );

                const data =
                    await response.json();

                if (
                    !response.ok ||
                    !data.success
                ) {

                    throw new Error(
                        data.error ||
                        "Failed to generate separate video."
                    );
                }

                console.log(
                    "Separate video generated:",
                    data.video_url
                );

                if (
                    window.showLightboxSeparateVideo
                ) {

                    window.showLightboxSeparateVideo(
                        data.video_url
                    );
                }
            } catch (error) {

                console.error(
                    "Separate video error:",
                    error
                );

                alert(
                    error.message ||
                    "Failed to generate separate video."
                );
            } finally {

                trackPersonBtn.disabled =
                    false;

                trackPersonBtn.textContent =
                    "Track Person";
            }
        }
    );
})();