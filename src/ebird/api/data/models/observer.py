from django.db import models
from django.utils.translation import gettext_lazy as _


class Observer(models.Model):
    class Meta:
        verbose_name = _("observer")
        verbose_name_plural = _("observers")

    identifier = models.CharField(
        max_length=15,
        primary_key=True,
        verbose_name=_("identifier"),
        help_text=_("The code for the person submitted the checklist."),
    )

    name = models.TextField(
        verbose_name=_("name"),
        help_text=_("The display name of the observer."),
    )

    original = models.TextField(
        verbose_name=_("original name"),
        help_text=_("The original name of the observer from eBird."),
    )

    enabled = models.BooleanField(
        default=True,
        verbose_name=_("Enabled"),
        help_text=_("Load checklists from the eBird observer."),
    )

    data = models.JSONField(
        verbose_name=_("Data"),
        help_text=_("Data describing an Observer."),
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
        return str(self.name)
