document.addEventListener("DOMContentLoaded", function () {
    const imageBtn = document.getElementById("toggle-image-btn");
    const videoBtn = document.getElementById("toggle-video-btn");
    const imagePanel = document.getElementById("image-panel");
    const videoPanel = document.getElementById("video-panel");

    if (
        !imageBtn ||
        !videoBtn ||
        !imagePanel ||
        !videoPanel
    ) {
        console.error("Mode toggle elements not found.");
        return;
    }

    function showPanel(mode) {
        const isImage = mode === "image";

        imagePanel.classList.toggle("active", isImage);
        videoPanel.classList.toggle("active", !isImage);

        imageBtn.classList.toggle("active", isImage);
        videoBtn.classList.toggle("active", !isImage);

        imageBtn.setAttribute(
            "aria-selected",
            isImage ? "true" : "false"
        );

        videoBtn.setAttribute(
            "aria-selected",
            isImage ? "false" : "true"
        );
    }

    imageBtn.addEventListener("click", function () {
        showPanel("image");
    });

    videoBtn.addEventListener("click", function () {
        showPanel("video");
    });
});