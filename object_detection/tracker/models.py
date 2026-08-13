from django.db import models


class TrackingReport(models.Model):
    input_video = models.CharField(max_length=500, blank=True)
    output_video = models.CharField(max_length=500)
    peak_persons_detected = models.PositiveIntegerField(default=0)
    total_visible_time = models.FloatField(null=True, blank=True)
    selected_track_id = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report #{self.pk} — {self.output_video}"


class PersonTrackStats(models.Model):
    report = models.ForeignKey(
        TrackingReport,
        on_delete=models.CASCADE,
        related_name="track_stats",
    )
    track_id = models.IntegerField()
    first_seen = models.FloatField()    
    last_seen = models.FloatField()
    visible_duration = models.FloatField()
    frames_seen = models.PositiveIntegerField()

    class Meta:
        ordering = ["track_id"]

    def __str__(self):
        return f"Track {self.track_id} (report #{self.report_id})"


class TrackFrameEvent(models.Model):
    track = models.ForeignKey(
        PersonTrackStats,
        on_delete=models.CASCADE,
        related_name="frame_events",
    )

    frame_number = models.PositiveIntegerField()
    timestamp = models.FloatField()
    full_frame_url = models.CharField(max_length=1000,blank=True,)
    cropped_image_url = models.CharField(max_length=1000,blank=True,)
    thumbnail_url = models.CharField(max_length=1000,blank=True,)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["frame_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["track", "frame_number"],
                name="unique_track_frame_event",
            )
        ]

    def __str__(self):
        return (
            f"Track {self.track.track_id} "
            f"— Frame {self.frame_number}"
        )
