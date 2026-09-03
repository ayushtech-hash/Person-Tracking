(function () {
    const overlay =
        document.getElementById("lightbox-overlay");

    const overlayImg =
        document.getElementById("lightbox-image");

    const overlayVideo =
        document.getElementById("lightbox-video");

    const overlayVideoSource =
        document.getElementById("lightbox-video-source");

    const overlayCaption =
        document.getElementById("lightbox-caption");

    const lightboxTitle =
        document.getElementById("lightbox-title");

    const closeBtn =
        document.getElementById("lightbox-close");

    const viewFullBtn =
        document.getElementById(
            "lightbox-view-full"
        );

    const loadingOverlay =
        document.getElementById("lightbox-loading");

    const loadingText =
        document.getElementById("lightbox-loading-text");

    const trackPersonBtn =
        document.getElementById(
            "lightbox-track-person"
        );

    const backPersonBtn =
        document.getElementById(
            "lightbox-back-person"
        );

    const trackGuide =
        document.getElementById(
            "lightbox-track-guide"
        );

    const trackedVideoGroups =
        document.getElementById("tracked-video-groups");

    const trackedVideoGroupList =
        document.getElementById("tracked-video-group-list");


    if (!overlay || !overlayImg || !closeBtn) {
        return;
    }


    // Track Person button is hidden initially.
    if (trackPersonBtn) {
        trackPersonBtn.style.display = "none";
    }


    // ---------------------------------------------------------
    // Track Person availability
    // ---------------------------------------------------------

    window.setTrackPersonAvailable =
        function (available) {

            if (!trackPersonBtn) {
                return;
            }

            trackPersonBtn.style.display =
                available
                    ? "inline-flex"
                    : "none";
        };


    // ---------------------------------------------------------
    // Current lightbox state
    // ---------------------------------------------------------

    let currentPersonImage = "";
    let currentFullFrameImage = "";
    let currentSeparateVideo = "";

    let currentTrackId = null;
    let currentReportId = null;


    let showingFullFrame = false;


    window.getLightboxTrackData = function () {
    return {
        trackId: currentTrackId,
        reportId: currentReportId
    };
};

    window.showLightboxVideoLoading = function (trackIds) {
        if (loadingText) {
            loadingText.textContent =
                Array.isArray(trackIds) && trackIds.length > 1
                    ? "Generating merged video…"
                    : "Generating tracked video…";
        }

        if (loadingOverlay) {
            loadingOverlay.style.display = "flex";
        }

        if (lightboxTitle) {
            lightboxTitle.textContent = "Preparing Video";
        }
    };

    window.hideLightboxVideoLoading = function () {
        if (loadingOverlay) {
            loadingOverlay.style.display = "none";
        }
    };

    function clearTrackedVideoGroups() {
        if (trackedVideoGroupList) {
            trackedVideoGroupList.innerHTML = "";
        }
        if (trackedVideoGroups) {
            trackedVideoGroups.style.display = "none";
        }
    }

    function renderTrackedVideoGroups(identityGroups) {
        clearTrackedVideoGroups();

        if (
            !trackedVideoGroups ||
            !trackedVideoGroupList ||
            !Array.isArray(identityGroups) ||
            !identityGroups.length
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
            trackedVideoGroupList.appendChild(groupElement);
        });

        if (trackedVideoGroupList.children.length) {
            trackedVideoGroups.style.display = "block";
        }
    }


    // ---------------------------------------------------------
    // Open Lightbox
    // ---------------------------------------------------------

    function openLightbox(
        thumbnailSrc,
        alt,
        caption,
        personCropSrc,
        fullFrameSrc,
        trackId,
        reportId
    ) {

        currentPersonImage =
            personCropSrc || thumbnailSrc;

        currentFullFrameImage =
            fullFrameSrc || "";

        currentTrackId =
            trackId || null;

        currentReportId =
            reportId || null;

        currentSeparateVideo = "";

        clearTrackedVideoGroups();

        window.hideLightboxVideoLoading();

        showingFullFrame = false;


        // IMPORTANT:
        // Open the FULL person crop,
        // NOT the upper-half thumbnail.

        overlayImg.src =
            currentPersonImage;

        overlayImg.alt =
            alt || "";

        overlayImg.style.display =
            "block";


        // Hide separate video.

        overlayVideo.pause();

        overlayVideoSource.src = "";

        overlayVideo.load();

        overlayVideo.style.display =
            "none";

        clearTrackedVideoGroups();


        overlayCaption.textContent =
            caption || "";


        if (viewFullBtn) {

            viewFullBtn.style.display =
                currentFullFrameImage
                    ? "inline-flex"
                    : "none";
        }


        if (backPersonBtn) {

            backPersonBtn.style.display =
                "none";
        }

        if (trackGuide && trackPersonBtn) {
            trackGuide.style.display =
                trackPersonBtn.style.display === "none"
                    ? "block"
                    : "none";
        }


        overlay.classList.add("open");

        document.body.style.overflow =
            "hidden";

        if (lightboxTitle) {
            lightboxTitle.textContent =
                "Person Crop";
        }
    }


    // ---------------------------------------------------------
    // Show Full Frame
    // ---------------------------------------------------------

    function showFullFrame() {

        if (!currentFullFrameImage) {
            return;
        }

        showingFullFrame = true;

        if (lightboxTitle) {
            lightboxTitle.textContent =
                "Full Frame";
        }


        overlayImg.style.display =
            "block";

        overlayVideo.style.display =
            "none";


        overlayImg.src =
            currentFullFrameImage;


        if (viewFullBtn) {

            viewFullBtn.style.display =
                "none";
        }


        if (backPersonBtn) {

            backPersonBtn.style.display =
                "inline-flex";
        }


        overlayCaption.textContent =
            overlayCaption.textContent.replace(
                " — Person Crop",
                ""
            ) + " — Full Frame";
    }


    // ---------------------------------------------------------
    // Show Person Crop
    // ---------------------------------------------------------

    function showPersonCrop() {

        overlayVideo.pause();

        overlayVideoSource.src = "";

        overlayVideo.load();

        overlayVideo.style.display =
            "none";

        overlayImg.style.display =
            "block";


        if (!currentPersonImage) {
            return;
        }


        showingFullFrame = false;

        if (lightboxTitle) {
            lightboxTitle.textContent =
                "Person Crop";
        }


        overlayImg.src =
            currentPersonImage;


        if (viewFullBtn) {

            viewFullBtn.style.display =
                currentFullFrameImage
                    ? "inline-flex"
                    : "none";
        }


        if (backPersonBtn) {

            backPersonBtn.style.display =
                "none";
        }

        if (trackGuide) {
            trackGuide.style.display = "none";
        }


        overlayCaption.textContent =
            overlayCaption.textContent.replace(
                " — Full Frame",
                ""
            );
    }


    // ---------------------------------------------------------
    // Show Separate Video
    // ---------------------------------------------------------

    window.showLightboxSeparateVideo = function (
        videoUrl,
        trackIds,
        identityGroups
    ) {
        if (!videoUrl) {
            return;
        }
    
        // Remember that we are currently showing
        // a separate video.
        currentSeparateVideo = videoUrl;

        window.hideLightboxVideoLoading();

        if (lightboxTitle) {
            lightboxTitle.textContent =
                "Tracked Person Video";
        }
    
        overlayImg.style.display = "none";
    
        overlayVideo.style.display = "block";
    
        overlayVideoSource.src = videoUrl;
    
        overlayVideo.load();
    
        overlayVideo.play().catch(function () {
            // Browser may block autoplay.
        });

        renderTrackedVideoGroups(identityGroups);
    
        overlayCaption.textContent =
            Array.isArray(trackIds) && trackIds.length > 1
                ? "Track IDs " + trackIds.join(", ") + " — Merged Video"
                : "Track ID " + currentTrackId + " — Separate Video";
    
        if (viewFullBtn) {
            viewFullBtn.style.display = "none";
        }
    
        if (backPersonBtn) {
            backPersonBtn.style.display = "none";
        }
    };

    // ---------------------------------------------------------
    // Close Lightbox
    // ---------------------------------------------------------

    function closeLightbox() {

        overlay.classList.remove("open");


        overlayVideo.pause();

        overlayVideoSource.src = "";

        overlayVideo.load();


        overlayImg.src = "";


        currentPersonImage = "";
        currentFullFrameImage = "";
        currentSeparateVideo = "";

        clearTrackedVideoGroups();

        window.hideLightboxVideoLoading();

        currentTrackId = null;
        currentReportId = null;

        showingFullFrame = false;


        document.body.style.overflow =
            "";
    }


    // ---------------------------------------------------------
    // Click on Thumbnail
    // ---------------------------------------------------------

    document.addEventListener(
        "click",
        function (event) {

            const image =
                event.target.closest(
                    ".new-track-event img"
                );

            if (!image) {
                return;
            }

            const trackCard =
                image.closest(
                    ".new-track-event"
                );

            if (!trackCard) {
                return;
            }

            const personCropSrc =
                image.dataset.personCrop ||
                image.src ||
                "";

            const fullFrameSrc =
                image.dataset.fullFrame ||
                "";

            const title =
                trackCard.querySelector(
                    ".new-track-event-title"
                );

            const meta =
                trackCard.querySelector(
                    ".new-track-event-meta"
                );

            let caption = "";

            if (title) {
                caption +=
                    title.textContent;
            }

            if (meta) {
                caption +=
                    " — " +
                    meta.textContent;
            }

            caption +=
                " — Person Crop";

            openLightbox(
                image.src,
                image.alt,
                caption,
                personCropSrc,
                fullFrameSrc,
                image.dataset.trackId,
                image.dataset.reportId
            );
        }
    );

    
    // ---------------------------------------------------------
    // View Full Frame
    // ---------------------------------------------------------

    if (viewFullBtn) {

        viewFullBtn.addEventListener(
            "click",
            function () {

                showFullFrame();

            }
        );
    }


    // ---------------------------------------------------------
    // Track Person
    // ---------------------------------------------------------
    //
    // TEMPORARILY kept here.
    //
    // We will move this into track-person.js
    // in the next step.
    //
    


    // ---------------------------------------------------------
    // Back to Person
    // ---------------------------------------------------------

    if (backPersonBtn) {

        backPersonBtn.addEventListener(
            "click",
            function () {

                showPersonCrop();

            }
        );
    }
    // ---------------------------------------------------------
    // Close Button
    // ---------------------------------------------------------

    closeBtn.addEventListener(
        "click",
        function () {

            if (currentSeparateVideo) {

                showPersonCrop();

                currentSeparateVideo = "";

                return;
            }


            closeLightbox();
        }
    );
    // ---------------------------------------------------------
    // Click outside lightbox
    // ---------------------------------------------------------

    overlay.addEventListener(
        "click",
        function (event) {

            if (
                event.target === overlay
            ) {

                closeLightbox();
            }
        }
    );

    // ---------------------------------------------------------
    // Escape key
    // ---------------------------------------------------------

    document.addEventListener(
        "keydown",
        function (event) {

            if (event.key === "Escape") {

                closeLightbox();
            }
        }
    );
    // ---------------------------------------------------------
    // Expose functions
    // ---------------------------------------------------------

    window.openLightbox =
        openLightbox;

})();
