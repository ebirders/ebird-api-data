from enum import StrEnum

from django.db import models
from django.utils.translation import gettext_lazy as _


class Checklist(models.Model):
    class Protocol(StrEnum):
        INCIDENTAL = "P20"
        STATIONARY = "P21"
        TRAVELING = "P22"
        AREA = "P23"
        BANDING = "P33"
        NOCTURNAL = "P54"
        PELAGIC = "P60"
        HISTORICAL = "P62"

    class Meta:
        verbose_name = _("checklist")
        verbose_name_plural = _("checklists")

    added = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("The date and time the checklist was added to eBird."),
        verbose_name=_("added"),
    )

    edited = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_("The date and time the eBird checklist was last edited."),
        verbose_name=_("edited"),
    )

    identifier = models.CharField(
        max_length=15,
        primary_key=True,
        verbose_name=_("identifier"),
        help_text=_("The unique identifier for the checklist."),
    )

    country = models.ForeignKey(
        "data.Country",
        related_name="checklists",
        on_delete=models.PROTECT,
        verbose_name=_("country"),
        help_text=_("The country where the checklist was made."),
    )

    state = models.ForeignKey(
        "data.State",
        related_name="checklists",
        on_delete=models.PROTECT,
        verbose_name=_("state"),
        help_text=_("The state where the checklist was made."),
    )

    county = models.ForeignKey(
        "data.County",
        blank=True,
        null=True,
        related_name="checklists",
        on_delete=models.PROTECT,
        verbose_name=_("county"),
        help_text=_("The county where the checklist was made."),
    )

    location = models.ForeignKey(
        "data.Location",
        related_name="checklists",
        on_delete=models.PROTECT,
        verbose_name=_("location"),
        help_text=_("The location where checklist was made."),
    )

    observer = models.ForeignKey(
        "data.Observer",
        related_name="checklists",
        on_delete=models.PROTECT,
        verbose_name=_("observer"),
        help_text=_("The person who submitted the checklist."),
    )

    observer_count = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_("observer count"),
        help_text=_("The total number of observers."),
    )

    species_count = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_("species count"),
        help_text=_("The number of species reported."),
    )

    date = models.DateField(
        db_index=True,
        verbose_name=_("date"),
        help_text=_("The date the checklist was started."),
    )

    time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_("time"),
        help_text=_("The time the checklist was started."),
    )

    started = models.DateTimeField(
        blank=True,
        db_index=True,
        null=True,
        verbose_name=_("date & time"),
        help_text=_("The date and time the checklist was started."),
    )

    protocol_code = models.TextField(
        blank=True,
        verbose_name=_("protocol code"),
        help_text=_("The code used to identify the protocol."),
    )

    project_code = models.TextField(
        blank=True,
        verbose_name=_("project code"),
        help_text=_("The code used to identify the project (portal)."),
    )

    duration = models.IntegerField(
        blank=True,
        null=True,
        verbose_name=_("duration"),
        help_text=_("The number of minutes spent counting."),
    )

    distance = models.DecimalField(
        blank=True,
        null=True,
        decimal_places=3,
        max_digits=6,
        verbose_name=_("distance"),
        help_text=_("The distance, in kilometres, covered while travelling."),
    )

    area = models.DecimalField(
        blank=True,
        null=True,
        decimal_places=3,
        max_digits=6,
        verbose_name=_("area"),
        help_text=_("The area covered, in hectares."),
    )

    complete = models.BooleanField(
        default=False,
        verbose_name=_("complete"),
        help_text=_("All species seen are reported."),
    )

    comments = models.TextField(
        blank=True,
        verbose_name=_("comments"),
        help_text=_("Any comments about the checklist."),
    )

    url = models.URLField(
        blank=True,
        verbose_name=_("url"),
        help_text=_("URL where the original checklist can be viewed."),
    )

    data = models.JSONField(
        verbose_name=_("Data"),
        help_text=_("Data describing a Checklist."),
        default=dict,
        blank=True,
    )

    created = models.DateTimeField(
        null=True, auto_now_add=True, help_text=_("When was the record created.")
    )

    modified = models.DateTimeField(
        null=True, auto_now=True, help_text=_("When was the record updated.")
    )

    def __repr__(self) -> str:
        return str(self.identifier)

    def __str__(self) -> str:
        return str(self.identifier)
