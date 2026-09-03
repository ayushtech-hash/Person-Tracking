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


class PersonIdentityGroup(models.Model):
    """One OSNet identity group within a single processed video/report."""

    report = models.ForeignKey(
        TrackingReport,
        on_delete=models.CASCADE,
        related_name="identity_groups",
    )
    # This is the stable, in-memory group key produced while processing the
    # upload.  It is unique only within its report.
    group_key = models.PositiveIntegerField()
    representative_track_id = models.IntegerField()
    is_active = models.BooleanField(default=True)
    merged_into = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        related_name="merged_groups",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["group_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["report", "group_key"],
                name="unique_report_identity_group",
            )
        ]

    def __str__(self):
        return (
            f"Identity group {self.group_key} "
            f"(report #{self.report_id})"
        )


class TrackSegment(models.Model):
    """One continuous, appearance-consistent use of a raw tracker ID.

    ByteTrack IDs are useful motion-track labels, but a single raw ID can
    switch to another player.  A segment is the unit that must later be used
    for identity grouping and separate-video generation.
    """

    report = models.ForeignKey(
        TrackingReport,
        on_delete=models.CASCADE,
        related_name="track_segments",
    )
    identity_group = models.ForeignKey(
        PersonIdentityGroup,
        on_delete=models.SET_NULL,
        related_name="segments",
        null=True,
        blank=True,
    )
    raw_track_id = models.IntegerField()
    segment_number = models.PositiveIntegerField()
    first_frame = models.PositiveIntegerField()
    last_frame = models.PositiveIntegerField()
    first_seen = models.FloatField()
    last_seen = models.FloatField()
    frames_seen = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    switch_reason = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["raw_track_id", "segment_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["report", "raw_track_id", "segment_number"],
                name="unique_report_raw_track_segment",
            )
        ]
        indexes = [
            models.Index(fields=["report", "raw_track_id"]),
        ]

    def __str__(self):
        return (
            f"Track {self.raw_track_id} / segment {self.segment_number} "
            f"(report #{self.report_id})"
        )


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
    separate_video_url = models.CharField(max_length=1000,blank=True,null=True,)
    identity_group = models.ForeignKey(
        PersonIdentityGroup,
        on_delete=models.SET_NULL,
        related_name="tracks",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["track_id"]

    def __str__(self):
        return f"Track {self.track_id} (report #{self.report_id})"


class ManualGroupingSuggestion(models.Model):
    """An OSNet similarity in the review range, awaiting user confirmation."""

    class Status:
        # Keep these plain constants because this project still supports a
        # Django version from before models.TextChoices was introduced.
        PENDING = "pending"
        DISMISSED = "dismissed"
        GROUPED = "grouped"

    STATUS_CHOICES = (
        (Status.PENDING, "Pending"),
        (Status.DISMISSED, "Dismissed"),
        (Status.GROUPED, "Grouped"),
    )

    report = models.ForeignKey(
        TrackingReport,
        on_delete=models.CASCADE,
        related_name="manual_grouping_suggestions",
    )
    first_group = models.ForeignKey(
        PersonIdentityGroup,
        on_delete=models.CASCADE,
        related_name="manual_suggestions_as_first",
    )
    second_group = models.ForeignKey(
        PersonIdentityGroup,
        on_delete=models.CASCADE,
        related_name="manual_suggestions_as_second",
    )
    first_track_id = models.IntegerField()
    first_frame_number = models.PositiveIntegerField()
    first_image_url = models.CharField(max_length=1000, blank=True)
    second_track_id = models.IntegerField()
    second_frame_number = models.PositiveIntegerField()
    second_image_url = models.CharField(max_length=1000, blank=True)
    similarity = models.FloatField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=Status.PENDING,
    )
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-similarity", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["report", "first_group", "second_group"],
                name="unique_manual_group_suggestion",
            )
        ]

    def __str__(self):
        return (
            f"Manual grouping suggestion {self.first_group_id}/"
            f"{self.second_group_id} ({self.similarity:.2f})"
        )


class ManualIdentityGroupMerge(models.Model):
    """The information required to reverse one user-confirmed group merge."""

    report = models.ForeignKey(
        TrackingReport,
        on_delete=models.CASCADE,
        related_name="manual_identity_group_merges",
    )
    source_suggestion = models.ForeignKey(
        ManualGroupingSuggestion,
        on_delete=models.SET_NULL,
        related_name="merge_history",
        null=True,
        blank=True,
    )
    primary_group = models.ForeignKey(
        PersonIdentityGroup,
        on_delete=models.PROTECT,
        related_name="merges_kept",
    )
    duplicate_group = models.ForeignKey(
        PersonIdentityGroup,
        on_delete=models.PROTECT,
        related_name="merges_absorbed",
    )
    moved_track_ids = models.TextField(default="[]")
    moved_segment_ids = models.TextField(default="[]")
    # Suggestions resolved by this exact merge. Keeping the IDs makes Undo
    # precise: it must not reopen suggestions resolved by a later merge.
    resolved_suggestion_ids = models.TextField(default="[]")
    is_undone = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    undone_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"Manual merge {self.primary_group_id}/"
            f"{self.duplicate_group_id}"
        )


class TrackFrameEvent(models.Model):
    track = models.ForeignKey(
        PersonTrackStats,
        on_delete=models.CASCADE,
        related_name="frame_events",
    )
    # Nullable during the rollout so all existing reports retain their
    # current raw-ID behaviour. New processing will populate this relation
    # once TrackSegmentManager is introduced.
    segment = models.ForeignKey(
        TrackSegment,
        on_delete=models.SET_NULL,
        related_name="frame_events",
        null=True,
        blank=True,
    )

    frame_number = models.PositiveIntegerField()
    timestamp = models.FloatField()
    full_frame_url = models.CharField(max_length=1000,blank=True,)
    cropped_image_url = models.CharField(max_length=1000,blank=True,)
    thumbnail_url = models.CharField(max_length=1000,blank=True,)
    # Coordinates are kept with the saved full frame so a generated
    # selected-person video can identify the person within that frame.
    bbox_x1 = models.IntegerField(null=True, blank=True)
    bbox_y1 = models.IntegerField(null=True, blank=True)
    bbox_x2 = models.IntegerField(null=True, blank=True)
    bbox_y2 = models.IntegerField(null=True, blank=True)
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
