(function () {
    const imageForm =
        document.getElementById("image-upload-form");

    const imageSubmitBtn =
        document.getElementById("image-submit-btn");

    const imageResultsSection =
        document.getElementById("image-results-section");

    const imageFormError =
        document.getElementById("image-form-error");


    function showImageFormError(message) {
        imageFormError.textContent = message;
        imageFormError.style.display = "block";
    }


    function hideImageFormError() {
        imageFormError.textContent = "";
        imageFormError.style.display = "none";
    }


    function renderImageResults(data) {

        const imageResultSection =
            document.getElementById("image-result-image");

        const imageResultsSection =
            document.getElementById("image-results-section");


        // -----------------------------
        // Detected Image
        // -----------------------------

        if (data.output_image) {

            imageResultSection.innerHTML =
                '<img class="result-image zoomable" ' +
                'src="' + data.output_image + '" ' +
                'alt="Detected persons">';

        } else {

            imageResultSection.innerHTML =
                '<div class="empty-state">' +
                    '<p>No detected image available.</p>' +
                '</div>';
        }


        // -----------------------------
        // Detection Result
        // -----------------------------

        let html =
            '<p class="success">Image processed successfully!</p>';

        html +=
            '<div class="stat-row">' +
                '<div class="stat-pill">' +
                    'Total Persons Detected' +
                    '<strong>' +
                        data.total_persons_detected +
                    '</strong>' +
                '</div>' +
            '</div>';


        // -----------------------------
        // Detection Table
        // -----------------------------

        if (
            data.detections &&
            data.detections.length > 0
        ) {

            html =
                html +
                '<div class="table-wrap">' +
                    '<table>';

            html +=
                '<tr>' +
                    '<th>Person</th>' +
                    '<th>Confidence</th>' +
                    '<th>Bounding Box (x1, y1, x2, y2)</th>' +
                '</tr>';

            data.detections.forEach(function (item) {

                html += '<tr>';

                html +=
                    '<td>' +
                        item.person_number +
                    '</td>';

                html +=
                    '<td>' +
                        item.confidence +
                    '</td>';

                html +=
                    '<td>' +
                        item.bbox.join(", ") +
                    '</td>';

                html += '</tr>';

            });

            html +=
                    '</table>' +
                '</div>';

        } else {

            html +=
                '<p>No persons were detected in this image.</p>';
        }


        imageResultsSection.innerHTML = html;
    }


    imageForm.addEventListener(
        "submit",
        async function (event) {

            event.preventDefault();

            hideImageFormError();

            imageResultsSection.innerHTML = "";

            imageSubmitBtn.disabled = true;

            imageSubmitBtn.textContent = "Detecting...";


            try {

                const formData =
                    new FormData(imageForm);

                const response =
                    await fetch(
                        imageForm.action,
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

                    let errorMessage =
                        "Image upload failed. Please check your input.";

                    if (data.errors) {

                        errorMessage =
                            Object.values(data.errors)
                                .flat()
                                .join(" ");

                    } else if (data.error) {

                        errorMessage =
                            data.error;
                    }

                    showImageFormError(
                        errorMessage
                    );

                    return;
                }


                renderImageResults(data);

                imageForm.reset();

            } catch (err) {

                showImageFormError(
                    "Request failed: " +
                    err.message
                );

            } finally {

                imageSubmitBtn.disabled = false;

                imageSubmitBtn.textContent =
                    "Detect Persons";
            }
        }
    );
})();