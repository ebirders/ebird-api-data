import logging

from django.db import models
from django.utils.translation import gettext_lazy as _

from .observation import Observation

log = logging.getLogger(__name__)


class Filter(models.Model):
    class Meta:
        verbose_name = _("filter")
        verbose_name_plural = _("filters")

    enabled = models.BooleanField(
        help_text=_("Is the filter active?"),
        verbose_name=_("enabled"),
    )

    name = models.TextField(
        verbose_name=_("name"), help_text=_("The name of the filter.")
    )

    species = models.ForeignKey(
        "data.Species",
        related_name="filtered_on",
        on_delete=models.CASCADE,
        verbose_name=_("species"),
        help_text=_("The species used to find matching Observations."),
    )

    country = models.ForeignKey(
        "data.Country",
        blank=True,
        null=True,
        related_name="filtered_on",
        on_delete=models.PROTECT,
        verbose_name=_("country"),
        help_text=_("The country where the observation was made."),
    )

    state = models.ForeignKey(
        "data.State",
        blank=True,
        null=True,
        related_name="filtered_on",
        on_delete=models.PROTECT,
        verbose_name=_("state"),
        help_text=_("The state where the observation was made."),
    )

    county = models.ForeignKey(
        "data.County",
        blank=True,
        null=True,
        related_name="filtered_on",
        on_delete=models.PROTECT,
        verbose_name=_("county"),
        help_text=_("The county where the observation was made."),
    )

    location = models.ForeignKey(
        "data.Location",
        blank=True,
        null=True,
        related_name="filtered_on",
        on_delete=models.CASCADE,
        verbose_name=_("location"),
        help_text=_("The location used to find matching Observations."),
    )

    update_species = models.ForeignKey(
        "data.Species",
        related_name="filtered_by",
        on_delete=models.CASCADE,
        verbose_name=_("update species"),
        help_text=_("Matching Observations are updated to this species."),
    )

    created = models.DateTimeField(
        null=True, auto_now_add=True, help_text=_("When was the record created.")
    )

    modified = models.DateTimeField(
        null=True, auto_now=True, help_text=_("When was the record updated.")
    )

    def __repr__(self) -> str:
        return str(self.name)

    def __str__(self) -> str:
        return str(self.name)

    def apply(self):
        count = 0
        filters = models.Q()

        if self.species:
            filters &= models.Q(species=self.species)

        if self.country:
            filters &= models.Q(country=self.country)
        elif self.state:
            filters &= models.Q(state=self.state)
        elif self.county:
            filters &= models.Q(county=self.county)
        elif self.location:
            filters &= models.Q(location=self.location)

        for observation in Observation.objects.filter(filters):
            observation.species = self.update_species
            observation.save()
            count += 1

        return count
