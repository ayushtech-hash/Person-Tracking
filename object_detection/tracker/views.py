# from services.video import seperate_video
from django.http import multipartparser
import os
import threading
import time
import cv2
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
from .models import TrackingReport,PersonTrackStats,TrackFrameEvent

from .services.detection.image_processor import ImageProcessor
from .services.processor import VideoProcessor
from .services.video.seperate_video import SeparateVideoGenerator
from .services.reporting.progress import progress
from .services.reporting.report_generator import ReportGenerator
from .services.video.video_paths import get_next_video_version, get_video_directories


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
    video_version,
    report_id,
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
    video_dirs = get_video_directories(video_version)
    event_dir = video_dirs["track_events"]
    crop_dir = video_dirs["track_crops"]

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
    f"{media_url}/videos/"
    f"{video_version}/track_events/"
    f"{full_filename}"
    )

    person_crop_url = (
    f"{media_url}/videos/"
    f"{video_version}/track_crops/"
    f"{person_filename}"
    )

    thumbnail_url = (
    f"{media_url}/videos/"
    f"{video_version}/track_crops/"
    f"{thumbnail_filename}"
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
        "report_id": report_id,

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



def update_track_frame(
    frame,
    tracked,
    frame_number,
    fps,
    report_id,
    video_version,

):
    """
    Save the processed full frame once and create a database
    event for every track visible in that frame.
    """
    
    
    video_dirs = get_video_directories(video_version)

    frame_dir = video_dirs["track_frames"]

    # ---------------------------------------------------------
    # Save the full frame ONCE
    # ---------------------------------------------------------

    filename = (
        f"report_{report_id}_frame_{frame_number}.jpg"
    )

    file_path = os.path.join(
        frame_dir,
        filename,
    )

    success = cv2.imwrite(
        file_path,
        frame,
    )

    if not success:
        print(
            f"ERROR: Failed to save track frame: {file_path}"
        )
        return

    full_frame_url = (
        f"{settings.MEDIA_URL.rstrip('/')}"
        f"/videos/{video_version}/track_frames/{filename}"
    )

    frame_time = (
        frame_number / fps
        if fps
        else 0
    )

    # ---------------------------------------------------------
    # Create event for EVERY active track
    # ---------------------------------------------------------


    report = TrackingReport.objects.get(
        id=report_id
    )

    for track in tracked:

        track_id = int(track.track_id)

        # Find/create stats row for this track
        track_stats, created = (
            PersonTrackStats.objects.get_or_create(
                report=report,
                track_id=track_id,
                defaults={
                    "first_seen": frame_time,
                    "last_seen": frame_time,
                    "visible_duration": 0,
                    "frames_seen": 0,
                },
            )
        )

        # Create frame event
        TrackFrameEvent.objects.get_or_create(
            track=track_stats,
            frame_number=frame_number,
            defaults={
                "timestamp": frame_time,
                "full_frame_url": full_frame_url,
            },
        )




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
    report_id,
    video_version,

):
    global _is_processing

    processing_start = time.time()

    close_old_connections()

    try:
        processor = VideoProcessor()

        def track_frame_handler(
            frame,
            tracked,
            frame_number,
            fps,
        ):
            update_track_frame(
                frame=frame,
                tracked=tracked,
                frame_number=frame_number,
                fps=fps,
                report_id=report_id,
                video_version=video_version,

            )
        report = processor.process(
            input_video=input_path,
            output_video=output_path,
            start_time=start_time,
            end_time=end_time,
            selected_track_id=track_id,
            progress_callback=update_progress,
            track_event_callback=update_track_event,
            track_frame_callback=track_frame_handler,
            video_version=video_version,
            report_id=report_id,

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

            # Create a new output workspace for this uploaded video
            video_version = get_next_video_version()

            video_dirs = get_video_directories(
                video_version
            )

            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "uploads"))
            filename = fs.save(video.name, video)

            input_path = os.path.join(settings.MEDIA_ROOT, "uploads", filename)
            output_filename = f"processed_{filename}"

            output_path = os.path.join(video_dirs["output_video"],output_filename,)
            input_video_url = (f"/media/uploads/{filename}")
            output_video_url = (
                f"/media/videos/"
                f"{video_version}/output_video/"
                f"{output_filename}"
            )

            tracking_report = ReportGenerator.create_processing_report(
                output_video_url=output_video_url,
                input_video_url=input_video_url,
                selected_track_id=track_id,
            )
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
                    tracking_report.id,
                    video_version,       


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

def generate_separate_video(request):
    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "error": "Method not allowed.",
            },
            status=405,
        )

    try:
        report_id = int(
            request.POST.get("report_id")
        )

        track_id = int(
            request.POST.get("track_id")
        )

    except (TypeError, ValueError):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid report_id or track_id.",
            },
            status=400,
        )

    try:
        report = TrackingReport.objects.get(
            id=report_id
        )
        parts = report.output_video.strip("/").split("/")

        video_version = parts[2]

        result = (
            SeparateVideoGenerator.generate(
                report_id=report_id,
                track_id=track_id,
                video_version=video_version
            )
        )

        return JsonResponse(
            {
                "success": True,
                **result,
            }
        )

    except ValueError as exc:
        return JsonResponse(
            {
                "success": False,
                "error": str(exc),
            },
            status=400,
        )

    except Exception as exc:
        return JsonResponse(
            {
                "success": False,
                "error": str(exc),
            },
            status=500,
        )

def test_separate_video(request):

    report_id = 3
    track_id = 1    

    try:
        report = TrackingReport.objects.get(
            id=report_id
        )
        parts = report.output_video.strip("/").split("/")

        video_version = parts[2]
        result = SeparateVideoGenerator.generate(
            report_id=report_id,
            track_id=track_id,
            video_version=video_version,

        )

        return JsonResponse({
            "success": True,
            **result,
        })

    except Exception as exc:
        return JsonResponse({
            "success": False,
            "error": str(exc),
        }, status=500)