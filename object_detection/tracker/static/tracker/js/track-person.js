(function () {
    const trackPersonBtn =
        document.getElementById(
            "lightbox-track-person"
        );

    const trackGuide =
        document.getElementById(
            "lightbox-track-guide"
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

            if (trackGuide) {
                trackGuide.style.display =
                    available ? "none" : "block";
            }
        };

    // ---------------------------------------------------------
    // Track Person
    // ---------------------------------------------------------

    window.generateSeparateVideo = async function (
        trackIds,
        reportId,
        triggerButton
    ) {
        const buttonLabel = triggerButton.textContent;
        triggerButton.disabled = true;
        triggerButton.textContent = "Generating...";

        if (window.showLightboxVideoLoading) {
            window.showLightboxVideoLoading(trackIds);
        }

        try {
            const formData = new FormData();

            if (trackIds.length > 1) {
                formData.append("track_ids", JSON.stringify(trackIds));
            } else {
                formData.append("track_id", trackIds[0]);
            }
            formData.append("report_id", reportId);

            const config = document.getElementById("app-config");
            const csrfToken = document.querySelector(
                "[name=csrfmiddlewaretoken]"
            );
            const response = await fetch(config.dataset.separateVideoUrl, {
                method: "POST",
                headers: {
                    "X-CSRFToken": csrfToken ? csrfToken.value : "",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: formData
            });
            const data = await response.json();

            if (!response.ok || !data.success) {
                throw new Error(
                    data.error || "Failed to generate separate video."
                );
            }

            console.log("Separate video generated:", data.video_url);
            if (window.showLightboxSeparateVideo) {
                window.showLightboxSeparateVideo(
                    data.video_url,
                    data.track_ids
                );
            }
        } catch (error) {
            if (window.hideLightboxVideoLoading) {
                window.hideLightboxVideoLoading();
            }
            console.error("Separate video error:", error);
            alert(error.message || "Failed to generate separate video.");
        } finally {
            triggerButton.disabled = false;
            triggerButton.textContent = buttonLabel;
        }
    };

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

            // A merged video is only requested when the thumbnail currently
            // open in the lightbox is itself selected. An unselected thumbnail
            // always retains the original single-person behaviour.
            const selectedTrackIds =
                window.getSelectedTrackIdsForLightbox
                    ? window.getSelectedTrackIdsForLightbox(
                        trackData.trackId
                    )
                    : [Number(trackData.trackId)];

            console.log(
                "Track Person request:",
                selectedTrackIds.length > 1
                    ? "merged track IDs " + selectedTrackIds.join(", ")
                    : "single track ID " + selectedTrackIds[0]
            );

            trackPersonBtn.disabled =
                true;

            trackPersonBtn.textContent =
                "Generating...";

            if (window.showLightboxVideoLoading) {
                window.showLightboxVideoLoading(selectedTrackIds);
            }


            try {

                const formData =
                    new FormData();


                if (selectedTrackIds.length > 1) {
                    formData.append(
                        "track_ids",
                        JSON.stringify(selectedTrackIds)
                    );
                } else {
                    formData.append(
                        "track_id",
                        selectedTrackIds[0]
                    );
                }

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
                        data.video_url,
                        data.track_ids
                    );
                }
            } catch (error) {

                if (window.hideLightboxVideoLoading) {
                    window.hideLightboxVideoLoading();
                }

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
