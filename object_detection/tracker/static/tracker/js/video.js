(function () {
    const form = document.getElementById("upload-form");
    if (!form) return;

    const submitBtn = document.getElementById("submit-btn");
    const progressSection = document.getElementById("progress-section");
    const progressBar = document.getElementById("progress-bar");
    const progressStatus = document.getElementById("progress-status");
    const progressPercent = document.getElementById("progress-percent");
    const progressFrames = document.getElementById("progress-frames");
    const processingTime = document.getElementById("processing-time");
    const processingTimeValue = document.getElementById("processing-time-value");
    const resultsSection = document.getElementById("results-section");
    const formError = document.getElementById("form-error");

    let pollInterval = null;
    let lastProgress = {
        current_frame: 0,
        total_frames: 0
    };

    let displayedTrackIds = new Set();
    let displayedSimilarityPairs = new Set();
    let isTrackSelectionEnabled = false;

    function setTrackSelectionEnabled(enabled) {
        isTrackSelectionEnabled = enabled;

        document.querySelectorAll(".new-track-event").forEach(
            function (card) {
                card.classList.toggle("selection-disabled", !enabled);
            }
        );

        const guide = document.getElementById("track-selection-guide");
        if (guide) {
            guide.classList.toggle("ready", enabled);
            guide.textContent = enabled
                ? "Processing is complete. Select thumbnails to track multiple IDs."
                : "You can track a person after video processing is complete. Then select thumbnails to track multiple IDs.";
        }

        if (!enabled) {
            document.querySelectorAll(".new-track-event.selected").forEach(
                function (card) {
                    card.classList.remove("selected");
                    card.dataset.selected = "false";
                }
            );
        }
        updateSelectedPeopleUI();
    }

    function updateSelectedPeopleUI() {
        const selectedCards = document.querySelectorAll(
            ".new-track-event.selected"
        );
        const selectionInfo = document.getElementById(
            "new-track-selection-info"
        );
        const selectionCount = document.getElementById(
            "new-track-selection-count"
        );
        const trackSelectedPeopleBtn = document.getElementById(
            "track-selected-people"
        );

        if (selectionCount) {
            selectionCount.textContent = selectedCards.length;
        }
        if (selectionInfo) {
            selectionInfo.style.display = selectedCards.length ? "flex" : "none";
        }
        if (trackSelectedPeopleBtn) {
            trackSelectedPeopleBtn.disabled = selectedCards.length === 0;
        }
    }


    function formatStatus(status) {
        const labels = {
            Processing: "Processing frames...",
            Converting: "Converting video for browser playback...",
            Completed: "Completed",
            Failed: "Failed",
        };

        return labels[status] || status || "Processing frames...";
    }


    function updateProgressUI(
        currentFrame,
        totalFrames,
        percent,
        status
    ) {
        lastProgress.current_frame = currentFrame;
        lastProgress.total_frames = totalFrames;

        progressBar.style.width = percent + "%";
        progressPercent.textContent = percent + "%";

        progressFrames.textContent =
            currentFrame +
            " / " +
            totalFrames +
            " frames processed";

        progressStatus.textContent =
            formatStatus(status);
    }


    function stopPolling() {
        if (pollInterval) {
            clearInterval(pollInterval);
            pollInterval = null;
        }
    }


    async function fetchProgress() {
        const config =
            document.getElementById("app-config");

        const response =
            await fetch(config.dataset.progressUrl);

        const contentType =
            response.headers.get("content-type") || "";

        if (!contentType.includes("application/json")) {
            throw new Error(
                "Server returned an unexpected response."
            );
        }

        return response.json();
    }


    function formatProcessingTime(seconds) {
        seconds = Math.round(seconds);

        const minutes =
            Math.floor(seconds / 60);

        const remainingSeconds =
            seconds % 60;

        if (minutes > 0) {
            return (
                minutes +
                " min " +
                remainingSeconds +
                " sec"
            );
        }

        return remainingSeconds + " sec";
    }


    function renderNewTrackEvents(events) {

        console.log(
            "NEW TRACK EVENTS FROM BACKEND:",
            events
        );

        const container =
            document.getElementById(
                "new-track-events"
            );

        const emptyState =
            document.getElementById(
                "new-track-empty"
            );

        if (
            !container ||
            !Array.isArray(events) ||
            events.length === 0
        ) {
            return;
        }

        events.forEach(function (event) {

            if (
                event == null ||
                event.track_id == null
            ) {
                return;
            }

            // Events are returned on every polling response. Render matches
            // before skipping an already-rendered tracking card.
            renderSimilarPeople(event);

            const trackId = String(event.track_id);
            const existingCard = Array.from(container.children).find(
                function (card) {
                    return card.dataset.trackId === trackId;
                }
            );

            // Processing begins with a temporary report. Once the completed
            // report is saved, polling returns its durable ID; update cards
            // already rendered during processing before they can be selected.
            if (existingCard && event.report_id != null) {
                existingCard.dataset.reportId = String(event.report_id);
                const existingImage = existingCard.querySelector("img");
                if (existingImage) {
                    existingImage.dataset.reportId = String(event.report_id);
                }
            }

            // A matched upper-half crop belongs to an existing OSNet group,
            // so it remains available in the backend but is not a separate
            // person for manual selection.  A later transitive match can
            // change an earlier representative into a group member; remove
            // that now-duplicate card on the next polling response.
            if (event.is_identity_representative === false) {
                if (existingCard) {
                    existingCard.remove();
                }
                displayedTrackIds.delete(trackId);
                return;
            }

            if (displayedTrackIds.has(trackId)) {
                return;
            }

            displayedTrackIds.add(
                trackId
            );


            const card =
                document.createElement("div");

            card.className = "new-track-event";
            card.classList.toggle("selection-disabled", !isTrackSelectionEnabled);
            card.dataset.trackId = String(event.track_id);
            card.dataset.reportId = String(event.report_id);
            if (event.identity_group_id !== undefined) {
                card.dataset.identityGroupId = String(event.identity_group_id);
            }
            card.dataset.selected = "false";

            const header =
                document.createElement("div");

            header.className =
                "new-track-event-header";


            const info =
                document.createElement("div");


            const title =
                document.createElement("div");

            title.className =
                "new-track-event-title";

            title.textContent =
                "New Track ID " +
                event.track_id;


            const meta =
                document.createElement("div");

            meta.className =
                "new-track-event-meta";


            const timeLabel =
                (
                    event.time_sec === undefined ||
                    event.time_sec === null
                )
                    ? ""
                    : " • " +
                      event.time_sec +
                      " sec";


            meta.textContent =
                "Frame " +
                event.frame +
                timeLabel;


            info.appendChild(title);
            info.appendChild(meta);


            const badge =
                document.createElement("span");

            badge.className =
                "new-track-badge";

            badge.textContent =
                "NEW ID";


            header.appendChild(info);
            header.appendChild(badge);

            card.appendChild(header);


            if (event.image_url) {

                const thumbWrap =
                    document.createElement("div");

                thumbWrap.className =
                    "thumb-wrap";


                const image =
                    document.createElement("img");


                const cacheBuster =
                    "t=" + Date.now();


                image.src =
                    event.image_url +
                    (
                        event.image_url.indexOf("?") === -1
                            ? "?"
                            : "&"
                    ) +
                    cacheBuster;


                if (event.person_crop_url) {

                    image.dataset.personCrop =
                        event.person_crop_url +
                        (
                            event.person_crop_url.indexOf("?") === -1
                                ? "?"
                                : "&"
                        ) +
                        cacheBuster;
                }


                image.alt =
                    "Tracked person - ID " +
                    event.track_id +
                    " at frame " +
                    event.frame;


                image.dataset.trackId =
                    event.track_id;

                image.dataset.reportId =
                    event.report_id;

                if (event.identity_group_id !== undefined) {
                    image.dataset.identityGroupId = event.identity_group_id;
                }


                image.loading = "lazy";


                if (event.full_frame_url) {

                    image.dataset.fullFrame =
                        event.full_frame_url +
                        (
                            event.full_frame_url.indexOf("?") === -1
                                ? "?"
                                : "&"
                        ) +
                        cacheBuster;
                }


                thumbWrap.appendChild(image);

                card.appendChild(thumbWrap);
            }

            card.addEventListener(
                "click",
                function (event) {
            
                    // Do not interfere with the existing
                    // thumbnail -> lightbox behavior.
                    if (event.target.closest("img")) {
                        return;
                    }

                    if (!isTrackSelectionEnabled) {
                        return;
                    }
            
                    const isSelected =
                        card.dataset.selected === "true";
            
                    card.dataset.selected =
                        isSelected ? "false" : "true";
            
                    card.classList.toggle(
                        "selected",
                        !isSelected
                    );
            
                    console.log(
                        "Track ID",
                        card.dataset.trackId,
                        !isSelected
                            ? "SELECTED"
                            : "DESELECTED"
                    );
                    updateSelectedPeopleUI();
                }
            );

            container.appendChild(card);
        });

        // An upload may contain only auto-matched events after a later group
        // merge.  Keep the empty state accurate in that case.
        if (emptyState) {
            emptyState.style.display = container.children.length ? "none" : "flex";
        }
        updateSelectedPeopleUI();
    }

    function renderSimilarPeople(event) {
        const matches = event.similar_persons;
        const container = document.getElementById("similar-person-matches");

        if (!container || !Array.isArray(matches) || !matches.length) {
            return;
        }

        matches.forEach(function (match) {
            const pair = [String(event.track_id), String(match.track_id)]
                .sort()
                .join(":");

            if (displayedSimilarityPairs.has(pair)) {
                return;
            }
            displayedSimilarityPairs.add(pair);

            const item = document.createElement("div");
            item.className = "similar-person-match";

            const title = document.createElement("div");
            title.className = "similar-person-match-title";
            title.textContent = "Likely same person";

            const score = document.createElement("span");
            score.textContent = " " + Math.round(Number(match.similarity) * 100) + "% match";
            title.appendChild(score);

            const images = document.createElement("div");
            images.className = "similar-person-images";
            [
                [match.image_url, "Similar person, track " + match.track_id],
                [event.image_url, "Current person, track " + event.track_id],
            ].forEach(function (imageData) {
                const image = document.createElement("img");
                image.src = imageData[0];
                image.alt = imageData[1];
                image.loading = "lazy";
                images.appendChild(image);
            });

            const meta = document.createElement("div");
            meta.className = "similar-person-match-meta";
            meta.textContent = "Track " + match.track_id + " (frame " +
                match.frame + ") and Track " + event.track_id +
                " (frame " + event.frame + ")";

            item.appendChild(title);
            item.appendChild(images);
            item.appendChild(meta);
            container.appendChild(item);
        });
    }

    window.getSelectedIdentityGroupIdsForLightbox =
        function (lightboxTrackId) {

            const currentCard = document.querySelector(
                '.new-track-event[data-track-id="' +
                String(lightboxTrackId) +
                '"]'
            );

            // An unselected lightbox card still represents its complete
            // OSNet group, not just the one internal tracker ID.
            if (!currentCard || !currentCard.classList.contains("selected")) {
                return currentCard
                    ? [Number(currentCard.dataset.identityGroupId)]
                    : [];
            }

            return Array.from(
                document.querySelectorAll(".new-track-event.selected")
            )
                .map(function (card) {
                    return Number(card.dataset.identityGroupId);
                })
                .filter(function (groupId) {
                    return Number.isInteger(groupId);
                })
                .filter(function (groupId, index, groupIds) {
                    return groupIds.indexOf(groupId) === index;
                })
                .sort(function (first, second) {
                    return first - second;
                });
        };

    function getSelectedCards() {
        return Array.from(
            document.querySelectorAll(".new-track-event.selected")
        );
    }

    const trackSelectedPeopleBtn =
        document.getElementById("track-selected-people");

    if (trackSelectedPeopleBtn) {
        trackSelectedPeopleBtn.addEventListener("click", function () {
            const selectedCards = getSelectedCards();
            const identityGroupIds = selectedCards
                .map(function (card) {
                    return Number(card.dataset.identityGroupId);
                })
                .filter(Number.isInteger)
                .sort(function (first, second) {
                    return first - second;
                });

            const reportIds = selectedCards
                .map(function (card) {
                    return card.dataset.reportId;
                })
                .filter(Boolean);

            if (!identityGroupIds.length || !reportIds.length) {
                alert("Select one or more tracked people first.");
                return;
            }

            if (new Set(reportIds).size !== 1) {
                alert("Selected people must belong to the same report.");
                return;
            }

            // Keep the existing generated-video experience in the lightbox.
            // The main page retains the original processed video and later
            // receives only the selected groups' upper-half crops.
            const firstImage = selectedCards[0].querySelector("img");
            if (firstImage) {
                firstImage.click();
            }

            if (window.generateSeparateVideo) {
                window.generateSeparateVideo(
                    identityGroupIds,
                    reportIds[0],
                    trackSelectedPeopleBtn
                );
            }
        });
    }


    function startPolling(
        onComplete,
        onFailed
    ) {

        stopPolling();

        pollInterval =
            setInterval(
                async function () {

                    try {

                        const data =
                            await fetchProgress();


                        updateProgressUI(
                            data.current_frame,
                            data.total_frames,
                            data.progress,
                            data.status
                        );


                        // Live new-track snapshots
                        // from the backend.
                        renderNewTrackEvents(
                            data.new_track_events || []
                        );


                        if (
                            data.status === "Completed"
                        ) {

                            stopPolling();

                            onComplete(data);

                        } else if (
                            data.status === "Failed"
                        ) {

                            stopPolling();

                            onFailed(data);
                        }

                    } catch (err) {

                        console.error(
                            "Failed to fetch progress:",
                            err
                        );
                    }

                },
                500
            );
    }


    function renderResults(data) {

        let html =
            '<p class="success">' +
            'Video uploaded and processed successfully!' +
            '</p>';


        if (data.output_video) {

            if (data.report) {

                if (data.report.reports) {

                    html +=
                        '<div class="stat-row">';

                    html +=
                        '<div class="stat-pill">' +
                        'Peak Persons Detected' +
                        '<strong>' +
                        data.report.peak_persons_detected +
                        '</strong>' +
                        '</div>';


                    html +=
                        '<div class="stat-pill">' +
                        'Total Visible Time' +
                        '<strong>' +
                        data.report.total_visible_time +
                        ' sec' +
                        '</strong>' +
                        '</div>';

                    html +=
                        '</div>';

                } else {

                    html +=
                        '<div class="stat-row">';

                    html +=
                        '<div class="stat-pill">' +
                        'Peak Persons Detected' +
                        '<strong>' +
                        data.report.peak_persons_detected +
                        '</strong>' +
                        '</div>';

                    html +=
                        '</div>';
                }


                html +=
                    '<h3>Tracking Report</h3>';


                if (data.report.reports) {

                    html +=
                        '<div class="table-wrap"><table>';

                    html +=
                        '<tr>' +
                        '<th>Track ID</th>' +
                        '<th>First Seen (sec)</th>' +
                        '<th>Last Seen (sec)</th>' +
                        '<th>Visible Duration (sec)</th>' +
                        '<th>Frames Seen</th>' +
                        '</tr>';


                    data.report.reports.forEach(
                        function (item) {

                            html += '<tr>';

                            html +=
                                '<td>' +
                                item.track_id +
                                '</td>';

                            html +=
                                '<td>' +
                                item.first_seen +
                                '</td>';

                            html +=
                                '<td>' +
                                item.last_seen +
                                '</td>';

                            html +=
                                '<td>' +
                                item.visible_duration +
                                '</td>';

                            html +=
                                '<td>' +
                                item.frames_seen +
                                '</td>';

                            html += '</tr>';
                        }
                    );


                    html +=
                        '</table></div>';

                } else {

                    html +=
                        '<div class="table-wrap"><table>';

                    html +=
                        '<tr>' +
                        '<th>Track ID</th>' +
                        '<td>' +
                        data.report.track_id +
                        '</td>' +
                        '</tr>';

                    html +=
                        '<tr>' +
                        '<th>First Seen (sec)</th>' +
                        '<td>' +
                        data.report.first_seen +
                        ' sec</td>' +
                        '</tr>';

                    html +=
                        '<tr>' +
                        '<th>Last Seen (sec)</th>' +
                        '<td>' +
                        data.report.last_seen +
                        ' sec</td>' +
                        '</tr>';

                    html +=
                        '<tr>' +
                        '<th>Visible Duration (sec)</th>' +
                        '<td>' +
                        data.report.visible_duration +
                        ' sec</td>' +
                        '</tr>';

                    html +=
                        '<tr>' +
                        '<th>Frames Seen</th>' +
                        '<td>' +
                        data.report.frames_seen +
                        '</td>' +
                        '</tr>';

                    html +=
                        '</table></div>';
                }
            }

        } else if (data.message) {

            html +=
                '<p class="error">' +
                data.message +
                '</p>';
        }


        resultsSection.innerHTML =
            html;


        const videoSection =
            document.getElementById(
                "video-result-section"
            );

        const videoContent =
            document.getElementById(
                "video-result-content"
            );


        if (
            data.output_video &&
            videoSection &&
            videoContent
        ) {

            videoContent.innerHTML =
                '<video width="700" controls>' +
                '<source src="' +
                data.output_video +
                '" type="video/mp4">' +
                'Your browser does not support the video tag.' +
                '</video>';

            videoSection.style.display =
                "block";
        }
    }


    function showFormError(message) {

        formError.textContent =
            message;

        formError.style.display =
            "block";
    }


    function hideFormError() {

        formError.textContent =
            "";

        formError.style.display =
            "none";
    }


    form.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();

            hideFormError();

            resultsSection.innerHTML =
                "";

            if (window.clearMainTrackedVideoGroups) {
                window.clearMainTrackedVideoGroups();
            }


            const videoSectionOnSubmit =
                document.getElementById(
                    "video-result-section"
                );

            if (videoSectionOnSubmit) {

                videoSectionOnSubmit.style.display =
                    "none";
            }


            progressSection.style.display =
                "block";

            submitBtn.disabled =
                true;


            lastProgress = {
                current_frame: 0,
                total_frames: 0
            };


            displayedTrackIds =
                new Set();

            displayedSimilarityPairs =
                new Set();

            const similarPeople = document.getElementById(
                "similar-person-matches"
            );
            if (similarPeople) {
                similarPeople.innerHTML = "";
            }


            const newTrackEvents =
                document.getElementById(
                    "new-track-events"
                );

            const newTrackEmpty =
                document.getElementById(
                    "new-track-empty"
                );


            if (newTrackEvents) {

                newTrackEvents.innerHTML =
                    "";
            }


            if (newTrackEmpty) {

                newTrackEmpty.style.display =
                    "flex";
            }

            // The cards were cleared for the next upload, so reset both the
            // count and the selected-people action before polling begins.
            setTrackSelectionEnabled(false);
            updateProgressUI(
                0,
                0,
                0,
                "Starting..."
            );
            const trackIdFieldOnSubmit =
                document.getElementById(
                    "track-id-field"
                );


            if (trackIdFieldOnSubmit) {

                trackIdFieldOnSubmit.classList.add(
                    "field-hidden"
                );
            }
            try {

                const formData =
                    new FormData(form);


                const response =
                    await fetch(
                        form.action || "",
                        {
                            method: "POST",
                            body: formData,
                            headers: {
                                "X-Requested-With":
                                    "XMLHttpRequest",
                            },
                        }
                    );


                const contentType =
                    response.headers.get(
                        "content-type"
                    ) || "";


                if (
                    !contentType.includes(
                        "application/json"
                    )
                ) {

                    throw new Error(
                        "Server returned an unexpected response. Please refresh and try again."
                    );
                }


                const data =
                    await response.json();


                if (
                    !response.ok ||
                    !data.success
                ) {

                    progressSection.style.display =
                        "none";

                    submitBtn.disabled =
                        false;


                    let errorMessage =
                        "Upload failed. Please check your input.";


                    if (data.errors) {

                        errorMessage =
                            Object.values(
                                data.errors
                            )
                            .flat()
                            .join(" ");

                    } else if (data.error) {

                        errorMessage =
                            data.error;
                    }


                    showFormError(
                        errorMessage
                    );

                    return;
                }


                if (
                    window.setTrackPersonAvailable
                ) {

                    window.setTrackPersonAvailable(
                        false
                    );
                }


                startPolling(

                    function onComplete(result) {

                        setTrackSelectionEnabled(true);

                        updateProgressUI(
                            result.total_frames,
                            result.total_frames,
                            100,
                            "Completed"
                        );


                        if (
                            window.setTrackPersonAvailable
                        ) {

                            window.setTrackPersonAvailable(
                                true
                            );
                        }


                        if (
                            result.processing_time !== null &&
                            result.processing_time !== undefined
                        ) {

                            processingTimeValue.textContent =
                                formatProcessingTime(
                                    result.processing_time
                                );

                            processingTime.style.display =
                                "block";
                        }


                        setTimeout(
                            function () {

                                progressSection.style.display =
                                    "none";

                                renderResults(
                                    result
                                );

                                submitBtn.disabled =
                                    false;

                                form.reset();


                            },
                            400
                        );
                    },


                    function onFailed(result) {

                        progressSection.style.display =
                            "none";

                        submitBtn.disabled =
                            false;

                        showFormError(
                            result.error ||
                            "Video processing failed."
                        );
                    }
                );

            } catch (err) {

                stopPolling();

                progressSection.style.display =
                    "none";

                submitBtn.disabled =
                    false;

                showFormError(
                    "Request failed: " +
                    err.message
                );
            }
        }
    );
})();
