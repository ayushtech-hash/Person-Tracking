import os

from django.conf import settings


def get_next_video_version():
    """
    Return the next video output version.

    Example:
        v1
        v2
        v3
    """

    videos_root = os.path.join(
        settings.MEDIA_ROOT,
        "videos",
    )

    os.makedirs(
        videos_root,
        exist_ok=True,
    )

    existing_versions = []

    for name in os.listdir(videos_root):
        if name.startswith("v") and name[1:].isdigit():
            existing_versions.append(
                int(name[1:])
            )

    next_number = (
        max(existing_versions) + 1
        if existing_versions
        else 1
    )

    return f"v{next_number}"


def get_video_directories(version):
    """
    Create and return all directories belonging
    to one uploaded video's processing output.
    """

    video_root = os.path.join(
        settings.MEDIA_ROOT,
        "videos",
        version,
    )

    directories = {
        "root": video_root,

        "output_video": os.path.join(
            video_root,
            "output_video",
        ),

        "separate_video": os.path.join(
            video_root,
            "separate_video",
        ),

        "track_events": os.path.join(
            video_root,
            "track_events",
        ),

        "track_crops": os.path.join(
            video_root,
            "track_crops",
        ),

        "upper_half_cropped": os.path.join(
            video_root,
            "upper_half_cropped",
        ),

        "track_frames": os.path.join(
            video_root,
            "track_frames",
        ),
    }

    for path in directories.values():
        os.makedirs(
            path,
            exist_ok=True,
        )

    return directories
