# from services.video import seperate_video
import json
from django.http import multipartparser
import os
import threading
import time
import cv2
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.db import close_old_connections, transaction
from django.db.models import Q
from django.utils import timezone
from django.http import JsonResponse
from django.shortcuts import render
from .forms import ImageUploadForm, VideoUploadForm
from .services.detection.image_processor import ImageProcessor
from .services.processor import VideoProcessor
from .services.reporting.progress import progress
from .services.reporting.report_generator import ReportGenerator
from .models import (
    ManualGroupingSuggestion,
    ManualIdentityGroupMerge,
    PersonIdentityGroup,
    PersonTrackStats,
    TrackFrameEvent,
    TrackingReport,
)

from .services.detection.image_processor import ImageProcessor
from .services.processor import VideoProcessor
from .services.video.seperate_video import SeparateVideoGenerator
from .services.reporting.progress import progress
from .services.reporting.report_generator import ReportGenerator
from .services.video.video_paths import get_next_video_version, get_video_directories
from .services.reidentification import PersonSimilarityIndex

from django.shortcuts import render
from .services.auth.decorators import jwt_login_required



_processing_lock = threading.Lock()
_is_processing = False



def login_page(request):
    return render(request, 'tracker/login.html')


def register_page(request):
    return render(request, 'tracker/register.html')


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
    similarity_index=None,
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
    upper_half_crop_dir = video_dirs["upper_half_cropped"]

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
    midpoint_y = y1 + ((y2 - y1) // 2)

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
        upper_half_crop_dir,
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
    f"{video_version}/upper_half_cropped/"
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
        "similar_persons": [],
    }

    # Use the same upper-half crop shown in the UI for ReID. Full person crops
    # are still saved separately for the lightbox and existing workflows.
    if similarity_index is not None:
        event["similar_persons"] = similarity_index.add_and_find_similar(
            thumbnail,
            event,
        )

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
        x1, y1, x2, y2 = map(int, track.bbox)

        # Match the coordinates to the saved frame, including clipping boxes
        # that lie partly outside its edges.
        frame_height, frame_width = frame.shape[:2]
        x1 = max(0, min(x1, frame_width - 1))
        y1 = max(0, min(y1, frame_height - 1))
        x2 = max(x1 + 1, min(x2, frame_width))
        y2 = max(y1 + 1, min(y2, frame_height))

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
                "bbox_x1": x1,
                "bbox_y1": y1,
                "bbox_x2": x2,
                "bbox_y2": y2,
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
    progress["manual_grouping_suggestions"] = []


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
        # Keep matches scoped to this upload, never across unrelated videos.
        similarity_index = PersonSimilarityIndex()

        def track_event_handler(**event_data):
            update_track_event(
                **event_data,
                similarity_index=similarity_index,
            )

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
            track_event_callback=track_event_handler,
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

        output_video_url = (
            f"/media/videos/"
            f"{video_version}/output_video/"
            f"{output_filename}"
        )        
        
        input_video_url = f"/media/uploads/{input_filename}"

        progress["output_video"] = output_video_url

        if report:
            tracking_report = ReportGenerator.save_to_database(
            report_data=report,
            output_video_url=output_video_url,
            input_video_url=input_video_url,
            selected_track_id=track_id,
            frame_events=progress.get("new_track_events",[]),
            # Resolve groups only after processing ends: a later upper-half
            # crop may have merged identities that initially looked separate.
            identity_groups=similarity_index.get_groups(),
            # Pairs in the 70%-to-auto-threshold range are persisted for the
            # manual grouping review UI added in the following step.
            manual_grouping_suggestions=(
                similarity_index.get_manual_grouping_suggestions()
            ),
            # Reuse the report that received every active-track frame while
            # processing; creating a second report loses the video timeline.
            tracking_report=TrackingReport.objects.get(id=report_id),
        )
            # Event cards are rendered while processing uses a temporary
            # report.  Replace that ID once the final report and its identity
            # groups have been persisted, before selection becomes available.
            for event in progress.get("new_track_events", []):
                event["report_id"] = tracking_report.id
            progress["report_id"] = tracking_report.id
            progress["report"] = ReportGenerator.serialize_tracking_report(
                tracking_report
            )
            progress["manual_grouping_suggestions"] = (
                _serialize_manual_grouping_suggestions(tracking_report)
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

@jwt_login_required
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


def _serialize_manual_grouping_suggestions(report):
    """Expose unresolved review-range OSNet pairs after processing completes."""
    return list(
        report.manual_grouping_suggestions.filter(
            is_resolved=False,
            status=ManualGroupingSuggestion.Status.PENDING,
        ).values(
            "id",
            "report_id",
            "first_group__group_key",
            "second_group__group_key",
            "first_track_id",
            "first_frame_number",
            "first_image_url",
            "second_track_id",
            "second_frame_number",
            "second_image_url",
            "similarity",
        )
    )


def _serialize_identity_groups_for_video(report, identity_group_ids):
    """Return upper-half snapshot crops for the groups used in one video."""
    groups = list(
        report.identity_groups.filter(
            group_key__in=identity_group_ids,
            is_active=True,
        ).prefetch_related("tracks__frame_events")
    )

    serialized_groups = []
    for group in groups:
        crops = []
        for track in group.tracks.all():
            # A thumbnail exists for the new-track snapshot that OSNet used
            # for matching. Per-frame events deliberately have no thumbnail.
            for event in track.frame_events.all():
                if not event.thumbnail_url:
                    continue
                crops.append(
                    {
                        "track_id": track.track_id,
                        "frame": event.frame_number,
                        "image_url": event.thumbnail_url,
                    }
                )

        crops.sort(key=lambda crop: (crop["frame"], crop["track_id"]))
        serialized_groups.append(
            {
                "identity_group_id": group.group_key,
                "representative_track_id": group.representative_track_id,
                "crops": crops,
            }
        )

    return serialized_groups


def _serialize_representative_event(report, group):
    """Return the persisted snapshot needed to restore one UI thumbnail."""
    event = (
        TrackFrameEvent.objects.filter(
            track__report=report,
            track__track_id=group.representative_track_id,
            thumbnail_url__gt="",
        )
        .order_by("frame_number", "id")
        .first()
    )
    if not event:
        return None

    return {
        "track_id": event.track.track_id,
        "report_id": report.id,
        "frame": event.frame_number,
        "time_sec": round(event.timestamp, 2),
        "image_url": event.thumbnail_url,
        "person_crop_url": event.cropped_image_url,
        "full_frame_url": event.full_frame_url,
        "identity_group_id": group.group_key,
        "is_identity_representative": True,
        "similar_persons": [],
    }


def dismiss_manual_grouping_suggestion(request):
    """Hide an irrelevant suggestion without changing either identity group."""
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Method not allowed."},
            status=405,
        )

    try:
        report_id = int(request.POST.get("report_id"))
        suggestion_id = int(request.POST.get("suggestion_id"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "Invalid report or suggestion."},
            status=400,
        )

    updated = ManualGroupingSuggestion.objects.filter(
        id=suggestion_id,
        report_id=report_id,
        is_resolved=False,
        status=ManualGroupingSuggestion.Status.PENDING,
    ).update(
        status=ManualGroupingSuggestion.Status.DISMISSED,
        is_resolved=True,
    )
    if not updated:
        return JsonResponse(
            {
                "success": False,
                "error": "This grouping suggestion is no longer available.",
            },
            status=404,
        )

    report = TrackingReport.objects.get(id=report_id)
    return JsonResponse(
        {
            "success": True,
            "remaining_suggestions": _serialize_manual_grouping_suggestions(report),
        }
    )


def merge_manual_identity_groups(request):
    """Merge the two groups shown by one confirmed manual suggestion."""
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Method not allowed."},
            status=405,
        )

    try:
        report_id = int(request.POST.get("report_id"))
        suggestion_id = int(request.POST.get("suggestion_id"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "Invalid report or suggestion."},
            status=400,
        )

    try:
        with transaction.atomic():
            suggestion = (
                ManualGroupingSuggestion.objects.select_for_update()
                .select_related("report", "first_group", "second_group")
                .get(
                    id=suggestion_id,
                    report_id=report_id,
                    is_resolved=False,
                    status=ManualGroupingSuggestion.Status.PENDING,
                )
            )
            first_group = suggestion.first_group
            second_group = suggestion.second_group

            # Group keys follow initial encounter order, so the lower key has
            # the earliest representative and remains visible after merging.
            primary_group, duplicate_group = sorted(
                (first_group, second_group),
                key=lambda group: group.group_key,
            )

            moved_track_ids = list(PersonTrackStats.objects.filter(
                report_id=report_id,
                identity_group=duplicate_group,
            ).values_list("track_id", flat=True))
            affected_suggestions = list(
                ManualGroupingSuggestion.objects.filter(
                    report_id=report_id,
                    status=ManualGroupingSuggestion.Status.PENDING,
                )
                .filter(
                    Q(first_group__in=[primary_group, duplicate_group])
                    | Q(second_group__in=[primary_group, duplicate_group])
                )
                .values_list("id", flat=True)
            )
            merge_history = ManualIdentityGroupMerge.objects.create(
                report_id=report_id,
                source_suggestion=suggestion,
                primary_group=primary_group,
                duplicate_group=duplicate_group,
                moved_track_ids=json.dumps(moved_track_ids),
                resolved_suggestion_ids=json.dumps(affected_suggestions),
            )
            PersonTrackStats.objects.filter(
                report_id=report_id,
                track_id__in=moved_track_ids,
            ).update(identity_group=primary_group)

            # Keep the original group for undo, but remove it from all active
            # behavior and from the representative-thumbnail list.
            duplicate_group.is_active = False
            duplicate_group.merged_into = primary_group
            duplicate_group.save(update_fields=["is_active", "merged_into"])

            # All review candidates involving either group are no longer
            # actionable once the user confirms this manual merge.
            ManualGroupingSuggestion.objects.filter(
                id__in=affected_suggestions,
            ).update(
                is_resolved=True,
                status=ManualGroupingSuggestion.Status.GROUPED,
            )

            serialized_report = ReportGenerator.serialize_tracking_report(
                suggestion.report
            )
            if progress.get("report_id") == report_id:
                progress["report"] = serialized_report

            return JsonResponse(
                {
                    "success": True,
                    "report_id": report_id,
                    "identity_group_id": primary_group.group_key,
                    "duplicate_identity_group_id": duplicate_group.group_key,
                    "representative_track_id": primary_group.representative_track_id,
                    "manual_merge_id": merge_history.id,
                    "output_video": suggestion.report.output_video,
                    "report": serialized_report,
                    "identity_groups": _serialize_identity_groups_for_video(
                        suggestion.report,
                        [primary_group.group_key],
                    ),
                    "remaining_suggestions": _serialize_manual_grouping_suggestions(
                        suggestion.report
                    ),
                }
            )

    except ManualGroupingSuggestion.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "error": "This grouping suggestion is no longer available.",
            },
            status=404,
        )


def undo_manual_identity_group_merge(request):
    """Reverse one confirmed manual merge without touching OSNet groups."""
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Method not allowed."}, status=405
        )

    try:
        report_id = int(request.POST.get("report_id"))
        merge_id = int(request.POST.get("manual_merge_id"))
    except (TypeError, ValueError):
        return JsonResponse(
            {"success": False, "error": "Invalid report or manual merge."},
            status=400,
        )

    try:
        with transaction.atomic():
            merge = (
                ManualIdentityGroupMerge.objects.select_for_update()
                .select_related("report", "primary_group", "duplicate_group")
                .get(id=merge_id, report_id=report_id, is_undone=False)
            )

            duplicate_group = merge.duplicate_group
            primary_group = merge.primary_group
            moved_track_ids = json.loads(merge.moved_track_ids)
            resolved_suggestion_ids = json.loads(merge.resolved_suggestion_ids)
            if duplicate_group.merged_into_id != primary_group.id:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "This merge can no longer be undone safely.",
                    },
                    status=409,
                )

            PersonTrackStats.objects.filter(
                report_id=report_id,
                track_id__in=moved_track_ids,
                identity_group=primary_group,
            ).update(identity_group=duplicate_group)
            duplicate_group.is_active = True
            duplicate_group.merged_into = None
            duplicate_group.save(update_fields=["is_active", "merged_into"])

            ManualGroupingSuggestion.objects.filter(
                id__in=resolved_suggestion_ids,
                status=ManualGroupingSuggestion.Status.GROUPED,
            ).update(
                is_resolved=False,
                status=ManualGroupingSuggestion.Status.PENDING,
            )
            merge.is_undone = True
            merge.undone_at = timezone.now()
            merge.save(update_fields=["is_undone", "undone_at"])

            serialized_report = ReportGenerator.serialize_tracking_report(
                merge.report
            )
            if progress.get("report_id") == report_id:
                progress["report"] = serialized_report

            return JsonResponse(
                {
                    "success": True,
                    "output_video": merge.report.output_video,
                    "report": serialized_report,
                    "restored_event": _serialize_representative_event(
                        merge.report, duplicate_group
                    ),
                    "remaining_suggestions": _serialize_manual_grouping_suggestions(
                        merge.report
                    ),
                }
            )
    except ManualIdentityGroupMerge.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "This manual merge is no longer available."},
            status=404,
        )


def merge_selected_identity_groups(request):
    """Permanently merge identity groups selected from the main thumbnails."""
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "error": "Method not allowed."},
            status=405,
        )

    try:
        report_id = int(request.POST.get("report_id"))
        identity_group_ids = sorted({
            int(group_id)
            for group_id in json.loads(request.POST.get("identity_group_ids"))
        })
        if len(identity_group_ids) < 2:
            raise ValueError
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse(
            {"success": False, "error": "Select at least two valid groups."},
            status=400,
        )

    try:
        with transaction.atomic():
            report = TrackingReport.objects.select_for_update().get(id=report_id)
            groups = list(
                PersonIdentityGroup.objects.select_for_update()
                .filter(
                    report=report,
                    group_key__in=identity_group_ids,
                    is_active=True,
                )
                .prefetch_related("tracks")
            )
            found_group_ids = {group.group_key for group in groups}
            missing_group_ids = set(identity_group_ids) - found_group_ids
            if missing_group_ids:
                missing_ids = ", ".join(
                    str(group_id) for group_id in sorted(missing_group_ids)
                )
                return JsonResponse(
                    {
                        "success": False,
                        "error": f"Identity group(s) not found: {missing_ids}.",
                    },
                    status=404,
                )

            group_track_ids = {
                group.id: [
                    track.track_id
                    for track in group.tracks.all()
                ]
                for group in groups
            }
            groups = [
                group for group in groups
                if group_track_ids.get(group.id)
            ]
            if len(groups) < 2:
                return JsonResponse(
                    {
                        "success": False,
                        "error": "At least two selected groups must contain tracks.",
                    },
                    status=400,
                )

            primary_group = min(
                groups,
                key=lambda group: min(group_track_ids[group.id]),
            )
            representative_track_id = min(
                track_id
                for track_ids in group_track_ids.values()
                for track_id in track_ids
            )
            duplicate_groups = [
                group for group in groups
                if group.id != primary_group.id
            ]
            duplicate_group_ids = [group.group_key for group in duplicate_groups]

            affected_suggestions = list(
                ManualGroupingSuggestion.objects.filter(
                    report=report,
                    status=ManualGroupingSuggestion.Status.PENDING,
                )
                .filter(
                    Q(first_group__in=groups) | Q(second_group__in=groups)
                )
                .values_list("id", flat=True)
            )

            merge_history_ids = []
            for duplicate_group in duplicate_groups:
                moved_track_ids = group_track_ids[duplicate_group.id]
                merge_history = ManualIdentityGroupMerge.objects.create(
                    report=report,
                    source_suggestion=None,
                    primary_group=primary_group,
                    duplicate_group=duplicate_group,
                    moved_track_ids=json.dumps(moved_track_ids),
                    resolved_suggestion_ids=json.dumps(affected_suggestions),
                )
                merge_history_ids.append(merge_history.id)
                PersonTrackStats.objects.filter(
                    report=report,
                    track_id__in=moved_track_ids,
                ).update(identity_group=primary_group)
                duplicate_group.is_active = False
                duplicate_group.merged_into = primary_group
                duplicate_group.save(update_fields=["is_active", "merged_into"])

            if primary_group.representative_track_id != representative_track_id:
                primary_group.representative_track_id = representative_track_id
                primary_group.save(update_fields=["representative_track_id"])

            ManualGroupingSuggestion.objects.filter(
                id__in=affected_suggestions,
            ).update(
                is_resolved=True,
                status=ManualGroupingSuggestion.Status.GROUPED,
            )

            serialized_report = ReportGenerator.serialize_tracking_report(report)
            if progress.get("report_id") == report_id:
                progress["report"] = serialized_report

            return JsonResponse(
                {
                    "success": True,
                    "report_id": report_id,
                    "identity_group_id": primary_group.group_key,
                    "duplicate_identity_group_ids": duplicate_group_ids,
                    "representative_track_id": representative_track_id,
                    "manual_merge_ids": merge_history_ids,
                    "output_video": report.output_video,
                    "report": serialized_report,
                    "representative_event": _serialize_representative_event(
                        report,
                        primary_group,
                    ),
                    "identity_groups": _serialize_identity_groups_for_video(
                        report,
                        [primary_group.group_key],
                    ),
                    "remaining_suggestions": _serialize_manual_grouping_suggestions(
                        report
                    ),
                }
            )
    except TrackingReport.DoesNotExist:
        return JsonResponse(
            {"success": False, "error": "Report not found."},
            status=404,
        )


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
        report_id = int(request.POST.get("report_id"))
        identity_group_ids_payload = request.POST.get("identity_group_ids")
        track_ids_payload = request.POST.get("track_ids")

        if identity_group_ids_payload:
            identity_group_ids = sorted({
                int(group_id)
                for group_id in json.loads(identity_group_ids_payload)
            })
            if not identity_group_ids:
                raise ValueError
            track_id = None
            track_ids = None
        elif track_ids_payload:
            track_ids = sorted({int(track_id) for track_id in json.loads(track_ids_payload)})
            if len(track_ids) < 2:
                raise ValueError
            track_id = None
            identity_group_ids = None
        else:
            track_id = int(request.POST.get("track_id"))
            track_ids = None
            identity_group_ids = None

    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid report_id or track ID selection.",
            },
            status=400,
        )

    try:
        report = TrackingReport.objects.get(
            id=report_id
        )

        if identity_group_ids:
            known_group_ids = set(
                report.identity_groups.filter(
                    group_key__in=identity_group_ids,
                    is_active=True,
                ).values_list("group_key", flat=True)
            )
            missing_group_ids = set(identity_group_ids) - known_group_ids
            if missing_group_ids:
                missing_ids = ", ".join(
                    str(group_id) for group_id in sorted(missing_group_ids)
                )
                raise ValueError(f"Identity group(s) not found: {missing_ids}.")

            # Expand each visible representative group into every internal
            # tracker ID that OSNet attached to it.
            resolved_track_ids = sorted(set(
                PersonTrackStats.objects.filter(
                    report_id=report_id,
                    identity_group__group_key__in=identity_group_ids,
                ).values_list("track_id", flat=True)
            ))
            if not resolved_track_ids:
                raise ValueError("No tracks found for the selected identity group(s).")

            parts = report.output_video.strip("/").split("/")
            video_version = parts[2]
            result = SeparateVideoGenerator.generate_merged(
                report_id=report_id,
                track_ids=resolved_track_ids,
                video_version=video_version,
            )

            return JsonResponse(
                {
                    "success": True,
                    **result,
                    "identity_group_ids": identity_group_ids,
                    "identity_groups": _serialize_identity_groups_for_video(
                        report,
                        identity_group_ids,
                    ),
                    "source": result.get("source", "generated"),
                }
            )

        if track_ids:
            print(
                f"[MERGED VIDEO] Requested track_ids={track_ids} "
                f"for report_id={report_id}"
            )
            known_track_ids = set(
                PersonTrackStats.objects.filter(
                    report_id=report_id,
                    track_id__in=track_ids,
                ).values_list("track_id", flat=True)
            )
            missing_track_ids = set(track_ids) - known_track_ids
            if missing_track_ids:
                missing_ids = ", ".join(
                    str(track_id) for track_id in sorted(missing_track_ids)
                )
                raise ValueError(f"Track ID(s) not found: {missing_ids}.")

            parts = report.output_video.strip("/").split("/")
            video_version = parts[2]
            result = SeparateVideoGenerator.generate_merged(
                report_id=report_id,
                track_ids=track_ids,
                video_version=video_version,
            )

            return JsonResponse(
                {
                    "success": True,
                    **result,
                    "source": result.get("source", "generated"),
                }
            )

        track_stats = PersonTrackStats.objects.get(
            report_id=report_id,
            track_id=track_id,
        )

        # ---------------------------------------------------------
        # CHECK DATABASE FIRST
        # ---------------------------------------------------------

        if (
            track_stats.separate_video_url
            and "_highlighted.mp4" in track_stats.separate_video_url
        ):

            print(
                f"[SEPARATE VIDEO] "
                f"Retrieved from DB | "
                f"report_id={report_id} | "
                f"track_id={track_id} | "
                f"url={track_stats.separate_video_url}"
            )

            return JsonResponse(
                {
                    "success": True,
                    "video_url": track_stats.separate_video_url,
                    "track_id": track_id,
                    "report_id": report_id,
                    "source": "database",
                }
            )

        # ---------------------------------------------------------
        # VIDEO NOT IN DATABASE → GENERATE
        # ---------------------------------------------------------

        print(
            f"[SEPARATE VIDEO] "
            f"Not found in DB. Generating... | "
            f"report_id={report_id} | "
            f"track_id={track_id}"
        )

        parts = report.output_video.strip("/").split("/")

        video_version = parts[2]

        result = SeparateVideoGenerator.generate(
            report_id=report_id,
            track_id=track_id,
            video_version=video_version,
        )

        # ---------------------------------------------------------
        # SAVE GENERATED VIDEO URL TO DATABASE
        # ---------------------------------------------------------

        track_stats.separate_video_url = result["video_url"]

        track_stats.save(
            update_fields=["separate_video_url"]
        )

        print(
            f"[SEPARATE VIDEO] "
            f"Generated and saved to DB | "
            f"report_id={report_id} | "
            f"track_id={track_id} | "
            f"url={result['video_url']}"
        )

        return JsonResponse(
            {
                "success": True,
                **result,
                "source": "generated",
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
