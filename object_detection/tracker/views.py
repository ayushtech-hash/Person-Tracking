import os
import threading
import time
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import close_old_connections
from django.http import JsonResponse
from django.shortcuts import render
from .forms import ImageUploadForm, VideoUploadForm
from .services.detection.image_processor import ImageProcessor
from .services.processor import VideoProcessor
from .services.reporting.progress import progress
from .services.reporting.report_generator import ReportGenerator
import cv2

_processing_lock = threading.Lock()
_is_processing = False


def is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def update_progress(current_frame, total_frames, status="Processing"):
    percent = int((current_frame / total_frames) * 100) if total_frames else 0

    progress["current_frame"] = current_frame
    progress["total_frames"] = total_frames
    progress["progress"] = percent
    progress["status"] = status

def update_track_event(
    frame,
    original_frame,
    bbox,
    track_id,
    frame_number,
    fps,
):
    """
    Save a new-track event with three images:

    1. Thumbnail:
       Upper half of the person's bounding box.

    2. Person crop:
       Full bounding-box crop with the bounding box visible.

    3. Full frame:
       Original video frame with the full tracking bounding box.
    """

    # ---------------------------------------------------------
    # Directories
    # ---------------------------------------------------------

    event_dir = os.path.join(
        settings.MEDIA_ROOT,
        "track_events"
    )

    crop_dir = os.path.join(
        settings.MEDIA_ROOT,
        "track_crops"
    )

    os.makedirs(event_dir, exist_ok=True)
    os.makedirs(crop_dir, exist_ok=True)

    # ---------------------------------------------------------
    # Bounding box
    # ---------------------------------------------------------

    x1, y1, x2, y2 = map(int, bbox)

    height, width = original_frame.shape[:2]

    # Keep coordinates inside image
    x1 = max(0, min(x1, width - 1))
    y1 = max(0, min(y1, height - 1))
    x2 = max(x1 + 1, min(x2, width))
    y2 = max(y1 + 1, min(y2, height))

    # ---------------------------------------------------------
    # 1. Save FULL FRAME with bounding box
    # ---------------------------------------------------------

    full_filename = (
        f"track_{track_id}_frame_{frame_number}_full.jpg"
    )

    full_file_path = os.path.join(
        event_dir,
        full_filename
    )

    success = cv2.imwrite(
        full_file_path,
        frame
    )

    if not success:
        print(
            f"ERROR: Failed to save full track event frame: "
            f"{full_file_path}"
        )
        return

    # ---------------------------------------------------------
    # 2. FULL PERSON CROP
    # ---------------------------------------------------------

    person_crop = original_frame[
        y1:y2,
        x1:x2
    ].copy()

    if person_crop.size == 0:
        print(
            f"ERROR: Empty person crop for "
            f"track ID={track_id}, frame={frame_number}"
        )
        return


    # Draw the bounding box around the cropped person.
    # Since this image is exactly the bounding-box region,
    # the box starts at (0, 0) and ends at the crop edges.

 
    person_filename = (
        f"track_{track_id}_frame_{frame_number}_person.jpg"
    )

    person_file_path = os.path.join(
        crop_dir,
        person_filename
    )

    success = cv2.imwrite(
        person_file_path,
        person_crop
    )

    if not success:
        print(
            f"ERROR: Failed to save person crop: "
            f"{person_file_path}"
        )
        return

    # ---------------------------------------------------------
    # 3. UPPER-HALF THUMBNAIL
    # ---------------------------------------------------------

    # Calculate the midpoint of the bounding box.
    midpoint_y = y1 + ((y2 - y1) // 4)

    # Crop only the upper half.
    thumbnail = original_frame[
        y1:midpoint_y,
        x1:x2
    ].copy()

    if thumbnail.size == 0:
        print(
            f"ERROR: Empty thumbnail for "
            f"track ID={track_id}, frame={frame_number}"
        )
        return

    thumbnail_height, thumbnail_width = thumbnail.shape[:2]

    # Draw the TOP portion of the bounding box.
    #
    # Since this thumbnail contains the upper half of the
    # bounding box, the visible rectangle goes from:
    # top-left = (0, 0)
    # bottom-left/right = bottom edge of thumbnail.
    #
    # This makes it visually clear that the thumbnail is
    # showing the upper part of the tracked bounding box.


    thumbnail_filename = (
        f"track_{track_id}_frame_{frame_number}_thumbnail.jpg"
    )

    thumbnail_file_path = os.path.join(
        crop_dir,
        thumbnail_filename
    )

    success = cv2.imwrite(
        thumbnail_file_path,
        thumbnail
    )

    if not success:
        print(
            f"ERROR: Failed to save thumbnail: "
            f"{thumbnail_file_path}"
        )
        return

    # ---------------------------------------------------------
    # 4. URLs
    # ---------------------------------------------------------

    media_url = settings.MEDIA_URL.rstrip("/")

    full_frame_url = (
        f"{media_url}/track_events/{full_filename}"
    )

    person_crop_url = (
        f"{media_url}/track_crops/{person_filename}"
    )

    thumbnail_url = (
        f"{media_url}/track_crops/{thumbnail_filename}"
    )

    # ---------------------------------------------------------
    # 5. Frame time
    # ---------------------------------------------------------

    frame_time = (
        frame_number / fps
        if fps
        else 0
    )

    # ---------------------------------------------------------
    # 6. Event data
    # ---------------------------------------------------------

    event = {
        "track_id": track_id,
        "frame": frame_number,
        "time_sec": round(frame_time, 2),

        # Card thumbnail
        "image_url": thumbnail_url,

        # Enlarged full bounding-box crop
        "person_crop_url": person_crop_url,

        # Original full frame
        "full_frame_url": full_frame_url,
    }

    if "new_track_events" not in progress:
        progress["new_track_events"] = []

    progress["new_track_events"].append(event)

    


def _reset_progress():
    progress["current_frame"] = 0
    progress["total_frames"] = 0
    progress["progress"] = 0
    progress["processing_time"] = None
    progress["status"] = "Processing"
    progress["output_video"] = None
    progress["report"] = None
    progress["report_id"] = None
    progress["message"] = None
    progress["error"] = None
    progress["new_track_events"] = []


def _run_processing(
    input_path,
    output_path,
    output_filename,
    input_filename,
    start_time,
    end_time,
    track_id,
):
    global _is_processing

    processing_start = time.time()

    close_old_connections()

    try:
        processor = VideoProcessor()
        report = processor.process(
            input_video=input_path,
            output_video=output_path,
            start_time=start_time,
            end_time=end_time,
            selected_track_id=track_id,
            progress_callback=update_progress,
            track_event_callback=update_track_event,
        )
        processing_end = time.time()

        processing_time = processing_end - processing_start

        progress["processing_time"] = round(
            processing_time,
            2
        )

        output_video_url = f"/media/outputs/{output_filename}"
        input_video_url = f"/media/uploads/{input_filename}"

        progress["output_video"] = output_video_url

        if report:
            tracking_report = ReportGenerator.save_to_database(
            report_data=report,
            output_video_url=output_video_url,
            input_video_url=input_video_url,
            selected_track_id=track_id,
            frame_events=progress.get("new_track_events",[]),
        )
            progress["report_id"] = tracking_report.id
            progress["report"] = ReportGenerator.serialize_tracking_report(
                tracking_report
            )
            progress["message"] = None
        else:
            progress["report_id"] = None
            progress["report"] = None
            progress["message"] = "Track ID was not found."
        progress["progress"] = 100
        progress["status"] = "Completed"
        
    except Exception as exc:
        progress["status"] = "Failed"
        progress["error"] = str(exc)
    finally:
        close_old_connections()
        with _processing_lock:
            _is_processing = False


def upload_video(request):
    global _is_processing

    if request.method == "POST":
        form = VideoUploadForm(request.POST, request.FILES)

        if form.is_valid():
            with _processing_lock:
                if _is_processing:
                    if is_ajax(request):
                        return JsonResponse(
                            {
                                "success": False,
                                "error": "A video is already being processed.",
                            },
                            status=409,
                        )
                    return render(
                        request,
                        "tracker/upload.html",
                        {
                            "form": form,
                            "image_form": ImageUploadForm(),
                            "error": "A video is already being processed.",
                        },
                    )
                _is_processing = True

            video = form.cleaned_data["video"]
            start_time = form.cleaned_data["start_time"] or None
            end_time = form.cleaned_data["end_time"] or None
            track_id = form.cleaned_data["track_id"]

            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "uploads"))
            filename = fs.save(video.name, video)

            input_path = os.path.join(settings.MEDIA_ROOT, "uploads", filename)
            output_filename = f"processed_{filename}"
            output_path = os.path.join(settings.MEDIA_ROOT, "outputs", output_filename)

            _reset_progress()

            thread = threading.Thread(
                target=_run_processing,
                args=(
                    input_path,
                    output_path,
                    output_filename,
                    filename,
                    start_time,
                    end_time,
                    track_id,
                ),
                daemon=True,
            )
            thread.start()

            if is_ajax(request):
                return JsonResponse({"success": True, "status": "Processing"})

            return render(
                request,
                "tracker/upload.html",
                {
                    "form": VideoUploadForm(),
                    "image_form": ImageUploadForm(),
                    "processing": True,
                },
            )

        if is_ajax(request):
            return JsonResponse(
                {"success": False, "errors": form.errors},
                status=400,
            )

    else:
        form = VideoUploadForm()

    return render(
        request,
        "tracker/upload.html",
        {
            "form": form,
            "image_form": ImageUploadForm(),
        },
    )


def detect_image(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)

    form = ImageUploadForm(request.POST, request.FILES)

    if not form.is_valid():
        return JsonResponse(
            {"success": False, "errors": form.errors},
            status=400,
        )

    image = form.cleaned_data["image"]

    fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "uploads"))
    filename = fs.save(image.name, image)

    input_path = os.path.join(settings.MEDIA_ROOT, "uploads", filename)
    output_filename = f"detected_{filename}"
    output_path = os.path.join(settings.MEDIA_ROOT, "outputs", output_filename)

    try:
        result = ImageProcessor.process(input_path, output_path)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=500)

    return JsonResponse(
        {
            "success": True,
            "output_image": f"/media/outputs/{output_filename}",
            "total_persons_detected": result["total_persons_detected"],
            "detections": result["detections"],
        }
    )


def get_progress(request):
    return JsonResponse(progress)
