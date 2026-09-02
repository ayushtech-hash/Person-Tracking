import copy
import threading


def _default_progress():
    return {
        "current_frame": 0,
        "total_frames": 0,
        "progress": 0,
        "processing_time": None,
        "status": "Idle",
        "output_video": None,
        "report": None,
        "report_id": None,
        "message": None,
        "error": None,
        "new_track_events": [],
        "manual_grouping_suggestions": [],
    }


progress_lock = threading.Lock()
progress_by_job = {}
active_job_by_user = {}
job_owner_by_job = {}


def start_user_job(user_id, job_id):
    with progress_lock:
        if user_id in active_job_by_user:
            return False

        active_job_by_user[user_id] = job_id
        job_owner_by_job[job_id] = user_id
        progress_by_job[job_id] = _default_progress()
        progress_by_job[job_id]["status"] = "Processing"
        return True


def finish_user_job(user_id, job_id):
    with progress_lock:
        if active_job_by_user.get(user_id) == job_id:
            del active_job_by_user[user_id]


def update_job_progress(job_id, **updates):
    with progress_lock:
        if job_id not in progress_by_job:
            progress_by_job[job_id] = _default_progress()

        progress_by_job[job_id].update(updates)


def append_new_track_event(job_id, event):
    with progress_lock:
        if job_id not in progress_by_job:
            progress_by_job[job_id] = _default_progress()

        progress_by_job[job_id].setdefault("new_track_events", []).append(event)


def get_job_progress(job_id, user_id=None):
    with progress_lock:
        if user_id is not None and job_owner_by_job.get(job_id) != user_id:
            return None

        job_progress = progress_by_job.get(job_id)
        if job_progress is None:
            return None

        return copy.deepcopy(job_progress)


def update_report_for_report_id(report_id, serialized_report):
    with progress_lock:
        for job_progress in progress_by_job.values():
            if job_progress.get("report_id") == report_id:
                job_progress["report"] = serialized_report
