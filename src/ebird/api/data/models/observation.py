import json
import logging

from json import JSONDecodeError

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

log = logging.getLogger(__name__)


class Observation(models.Model):
    class Meta:
        verbose_name = _("observation")
        verbose_name_plural = _("observations")

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
        help_text=_("A global unique identifier for the observation."),
    )

    checklist = models.ForeignKey(
        "data.Checklist",
        related_name="observations",
        on_delete=models.CASCADE,
        verbose_name=_("checklist"),
        help_text=_("The checklist this observation belongs to."),
    )

    species = models.ForeignKey(
        "data.Species",
        related_name="observations",
        on_delete=models.PROTECT,
        verbose_name=_("species"),
        help_text=_("The identified species."),
    )

    observer = models.ForeignKey(
        "data.Observer",
        related_name="observations",
        on_delete=models.PROTECT,
        verbose_name=_("observer"),
        help_text=_("The person who made the observation."),
    )

    country = models.ForeignKey(
        "data.Country",
        related_name="observations",
        on_delete=models.PROTECT,
        verbose_name=_("country"),
        help_text=_("The country where the observation was made."),
    )

    state = models.ForeignKey(
        "data.State",
        related_name="observations",
        on_delete=models.PROTECT,
        verbose_name=_("state"),
        help_text=_("The state where the observation was made."),
    )

    county = models.ForeignKey(
        "data.County",
        blank=True,
        null=True,
        related_name="observations",
        on_delete=models.PROTECT,
        verbose_name=_("county"),
        help_text=_("The county where the observation was made."),
    )

    location = models.ForeignKey(
        "data.Location",
        related_name="observations",
        on_delete=models.PROTECT,
        verbose_name=_("location"),
        help_text=_("The location where the observation was made."),
    )

    date = models.DateField(
        db_index=True,
        verbose_name=_("date"),
        help_text=_("The date the observation was made."),
    )

    time = models.TimeField(
        blank=True,
        null=True,
        verbose_name=_("time"),
        help_text=_("The time the observation was made."),
    )

    started = models.DateTimeField(
        blank=True,
        db_index=True,
        null=True,
        verbose_name=_("date & time"),
        help_text=_("The date and time the observation was made."),
    )

    count = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name=_("count"),
        help_text=_("The number of birds seen."),
    )

    audio = models.BooleanField(
        default=False,
        verbose_name=_("has audio"),
        help_text=_("Have audio recordings been uploaded to the Macaulay library."),
    )

    photo = models.BooleanField(
        default=False,
        verbose_name=_("has photos"),
        help_text=_("Have photos been uploaded to the Macaulay library."),
    )

    video = models.BooleanField(
        default=False,
        verbose_name=_("has video"),
        help_text=_("Have video recordings been uploaded to the Macaulay library."),
    )

    approved = models.BooleanField(
        default=True,
        verbose_name=_("Approved"),
        help_text=_("Has the observation been accepted."),
    )

    reason = models.TextField(
        blank=True,
        verbose_name=_("Reason"),
        help_text=_(
            "The reason given for the observation to be marked as not approved."
        ),
    )

    comments = models.TextField(
        blank=True,
        verbose_name=_("comments"),
        help_text=_("Any comments about the observation."),
    )

    urn = models.TextField(
        blank=True,
        verbose_name=_("URN"),
        help_text=_("The globally unique identifier for the observation."),
    )

    data = models.JSONField(
        verbose_name=_("Data"),
        help_text=_("Data describing an Observation."),
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

    def get_reason(self) -> str:
        try:
            data = json.loads(self.reason)
            reason = data.get(get_language(), "")
        except JSONDecodeError:
            log.error("Incorrect JSON for Observation reason: %s", self.id)
            reason = ""
        return reason

    def has_media(self):
        return self.audio or self.photo or self.video
