(function () {
    const trackPersonBtn =
        document.getElementById(
            "lightbox-track-person"
        );

    const trackGuide =
        document.getElementById(
            "lightbox-track-guide"
        );

    const mainVideoSection =
        document.getElementById("video-result-section");

    const mainTrackedVideoGroups =
        document.getElementById("tracked-video-groups-main");

    const mainTrackedVideoGroupList =
        document.getElementById("tracked-video-group-list-main");

    if (!trackPersonBtn) {
        return;
    }

    trackPersonBtn.style.display = "none";

    function clearMainTrackedVideoGroups() {
        if (mainTrackedVideoGroupList) {
            mainTrackedVideoGroupList.innerHTML = "";
        }
        if (mainTrackedVideoGroups) {
            mainTrackedVideoGroups.style.display = "none";
        }
    }

    function renderMainTrackedVideoGroups(identityGroups) {
        clearMainTrackedVideoGroups();

        if (
            !mainTrackedVideoGroups ||
            !mainTrackedVideoGroupList ||
            !Array.isArray(identityGroups)
        ) {
            return;
        }

        identityGroups.forEach(function (group) {
            const crops = Array.isArray(group.crops) ? group.crops : [];
            if (!crops.length) {
                return;
            }

            const groupElement = document.createElement("section");
            groupElement.className = "tracked-video-group";

            const heading = document.createElement("h4");
            heading.textContent =
                "Group " + group.identity_group_id +
                " · representative track " + group.representative_track_id;
            groupElement.appendChild(heading);

            const cropList = document.createElement("div");
            cropList.className = "tracked-video-group-crops";
            crops.forEach(function (crop) {
                const cropItem = document.createElement("figure");
                const image = document.createElement("img");
                image.src = crop.image_url;
                image.alt =
                    "Upper-half crop for track " + crop.track_id +
                    " at frame " + crop.frame;
                image.loading = "lazy";

                const caption = document.createElement("figcaption");
                caption.textContent =
                    "Track " + crop.track_id + " · frame " + crop.frame;

                cropItem.appendChild(image);
                cropItem.appendChild(caption);
                cropList.appendChild(cropItem);
            });

            groupElement.appendChild(cropList);
            mainTrackedVideoGroupList.appendChild(groupElement);
        });

        if (mainTrackedVideoGroupList.children.length) {
            mainTrackedVideoGroups.style.display = "block";
        }
    }

    window.clearMainTrackedVideoGroups = clearMainTrackedVideoGroups;

    function showTrackedVideoGroupsOnPage(identityGroups) {
        // The generated selected-person video stays in the lightbox.  Do not
        // replace the original processed video in the main Tracked Video card.
        if (mainVideoSection) {
            mainVideoSection.style.display = "block";
        }
        renderMainTrackedVideoGroups(identityGroups);
    }


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
        identityGroupIds,
        reportId,
        triggerButton
    ) {
        const buttonLabel = triggerButton.textContent;
        triggerButton.disabled = true;
        triggerButton.textContent = "Generating...";

        if (window.showLightboxVideoLoading) {
            window.showLightboxVideoLoading(identityGroupIds);
        }

        try {
            const formData = new FormData();

            formData.append(
                "identity_group_ids",
                JSON.stringify(identityGroupIds)
            );
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
            showTrackedVideoGroupsOnPage(data.identity_groups);
            if (window.showLightboxSeparateVideo) {
                window.showLightboxSeparateVideo(
                    data.video_url,
                    data.track_ids,
                    []
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
            const selectedIdentityGroupIds =
                window.getSelectedIdentityGroupIdsForLightbox
                    ? window.getSelectedIdentityGroupIdsForLightbox(
                        trackData.trackId
                    )
                    : [];

            if (!selectedIdentityGroupIds.length) {
                alert("This thumbnail does not have an OSNet identity group.");
                return;
            }

            console.log(
                "Track Person request:",
                "identity groups " + selectedIdentityGroupIds.join(", ")
            );

            trackPersonBtn.disabled =
                true;

            trackPersonBtn.textContent =
                "Generating...";

            if (window.showLightboxVideoLoading) {
                window.showLightboxVideoLoading(selectedIdentityGroupIds);
            }


            try {

                const formData =
                    new FormData();


                formData.append(
                    "identity_group_ids",
                    JSON.stringify(selectedIdentityGroupIds)
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
                showTrackedVideoGroupsOnPage(data.identity_groups);

                if (
                    window.showLightboxSeparateVideo
                ) {

                    window.showLightboxSeparateVideo(
                        data.video_url,
                        data.track_ids,
                        []
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
