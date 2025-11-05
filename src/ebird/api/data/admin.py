from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.widgets import AutocompleteSelect
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.db.models import DecimalField, IntegerField, TextField
from django.forms import ModelForm, Textarea, TextInput
from django.urls import path, reverse, reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views import generic

from . import models
from .fields import TranslationCharField, TranslationTextField
from .loaders import APILoader
from .models import Observation, Species, Checklist


class ObservationInline(admin.TabularInline):
    model = models.Observation
    fields = ("observation", "common_name", "scientific_name", "count", "comments")
    ordering = ("species__order",)
    readonly_fields = ("observation", "common_name", "scientific_name", "count", "comments")
    extra = 0

    @admin.display(description=_("Observation"))
    def observation(self, obj):
        url = reverse("admin:data_observation_change", kwargs={"object_id": obj.id})
        return format_html('<a href="{}">{}</a>', url, obj.identifier)

    @admin.display(description=_("Common name"))
    def common_name(self, obj):
        return obj.species.get_common_name()

    @admin.display(description=_("Scientific name"))
    def scientific_name(self, obj):
        return format_html("<i>{}</i>", obj.species.scientific_name)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("species")
            .order_by("species__taxon_order")
        )

@admin.register(models.Checklist)
class ChecklistAdmin(admin.ModelAdmin):
    list_display = (
        "identifier",
        "date",
        "time",
        "species_count",
        "location",
        "observer",
    )
    ordering = ("-started",)
    search_fields = ("identifier", "location__name", "observer__name")
    autocomplete_fields = ("location", "observer")
    inlines = [ObservationInline]
    formfield_overrides = {
        DecimalField: {
            "widget": TextInput(),
        },
        IntegerField: {
            "widget": TextInput(),
        },
        TextField: {
            "widget": TextInput(attrs={"class": "vTextField"}),
        },
    }
    readonly_fields = ("identifier", "edited")
    fields = (
        "date",
        "time",
        "location",
        "observer",
        "species_count",
        "complete",
        "observer_count",
        "protocol_code",
        "duration",
        "distance",
        "comments",
        "data",
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "comments":
            field.widget = Textarea(attrs={"rows": 5, "class": "vLargeTextField"})
        elif db_field.name == "data":
            field.widget = Textarea(attrs={"rows": 10, "class": "vLargeTextField"})

        return field

    def save_model(self, request, obj, form, change):
        if "location" in form.changed_data:
            location = obj.location
            obj.country = location.country
            obj.state = location.state
            obj.county = location.county
        super().save_model(request, obj, form, change)


@admin.register(models.Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    ordering = ("code",)
    readonly_fields = ("code",)
    formfield_overrides = {
        TextField: {
            "widget": TextInput(attrs={"class": "vTextField"}),
        }
    }


@admin.register(models.State)
class StateAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    ordering = ("code",)
    readonly_fields = ("code",)
    formfield_overrides = {
        TextField: {
            "widget": TextInput(attrs={"class": "vTextField"}),
        }
    }


@admin.register(models.County)
class CountyAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    ordering = ("code",)
    readonly_fields = ("code",)
    formfield_overrides = {
        TextField: {
            "widget": TextInput(attrs={"class": "vTextField"}),
        }
    }


@admin.register(models.Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("identifier", "name", "county", "state", "country")
    list_select_related = ("country", "county", "state")
    ordering = ("-identifier",)
    search_fields = (
        "identifier",
        "name",
        "county__name",
        "state__name",
        "country__name",
    )
    readonly_fields = ("identifier",)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "original":
            field.widget = TextInput(attrs={"class": "vLargeTextField"})
        elif db_field.name == "name":
            field.widget = TextInput(attrs={"class": "vLargeTextField"})
        elif db_field.name == "latitude":
            field.widget = TextInput()
        elif db_field.name == "longitude":
            field.widget = TextInput()
        elif db_field.name == "data":
            field.widget = Textarea(attrs={"rows": 10, "class": "vLargeTextField"})
        return field

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if "country" in form.changed_data:
            models.Checklist.objects.filter(location=obj).update(country=obj.country)
            models.Observation.objects.filter(location=obj).update(country=obj.country)
        if "state" in form.changed_data:
            models.Checklist.objects.filter(location=obj).update(state=obj.state)
            models.Observation.objects.filter(location=obj).update(state=obj.state)
        if "county" in form.changed_data:
            models.Checklist.objects.filter(location=obj).update(county=obj.county)
            models.Observation.objects.filter(location=obj).update(county=obj.county)


class ChangeSpeciesForm(forms.Form):
    species = forms.ModelChoiceField(
        queryset=Species.objects.all(),
        widget=AutocompleteSelect(Observation._meta.get_field("species"), admin.site),
    )


class ObservationForm(ModelForm):
    reason = TranslationTextField(required=False)

    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].widget.attrs.update({"rows": 2})


@admin.register(models.Observation)
class ObservationAdmin(admin.ModelAdmin):
    list_display = (
        "common_name",
        "count",
        "date",
        "time",
        "location",
        "observer",
    )
    search_fields = (
        "identifier",
        "species__common_name",
        "species__scientific_name",
        "observer__name",
    )
    list_filter = (
        "audio",
        "photo",
        "video",
        "approved",
    )
    ordering = ("-checklist__started",)
    form = ObservationForm
    autocomplete_fields = ("checklist", "location", "observer", "species")
    readonly_fields = ("identifier", "edited")
    fields = (
        "species",
        "count",
        "audio",
        "photo",
        "video",
        "comments",
        "checklist",
        "location",
        "observer",
        "edited",
        "approved",
        "reason",
        "data",
    )

    @admin.display(description=_("Species"))
    def common_name(self, obj):
        return obj.species.get_common_name()

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "count":
            field.widget = TextInput()
        elif db_field.name == "comments":
            field.widget = Textarea(attrs={"rows": 5, "class": "vLargeTextField"})
        elif db_field.name == "data":
            field.widget = Textarea(attrs={"rows": 5, "class": "vLargeTextField"})
        return field

    def save_model(self, request, obj, form, change):
        if "location" in form.changed_data:
            location = obj.location
            obj.country = location.country
            obj.state = location.state
            obj.county = location.county

        super().save_model(request, obj, form, change)


@admin.register(models.Observer)
class ObserverAdmin(admin.ModelAdmin):
    list_display = ("name", "identifier", "multiple", "enabled")
    ordering = ("name",)
    search_fields = ("name", "identifier")
    list_filter = ("multiple", "enabled")
    form = ObservationForm

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "original":
            field.widget = TextInput(attrs={"class": "vTextField"})
        elif db_field.name == "name":
            field.widget = TextInput(attrs={"class": "vTextField"})
        elif db_field.name == "data":
            field.widget = Textarea(attrs={"rows": 5, "class": "vLargeTextField"})
        return field


class FetchSpeciesForm(forms.Form):
    species_code = forms.CharField(
        help_text=_("The eBird code for the species, e.g. cangoo, for Canada Goose.")
    )


class FetchSpeciesView(PermissionRequiredMixin, generic.FormView):
    form_class = FetchSpeciesForm
    permission_required = "data.add_species"
    success_url = reverse_lazy("admin:data_species_changelist")
    template_name = "admin/data/species/fetch_species.html"

    def form_valid(self, form):
        self.fetch_species(form)
        return super().form_valid(form)

    def fetch_species(self, form):
        species_code = form.cleaned_data["species_code"]
        key: str = getattr(settings, "EBIRD_API_KEY")
        locales: dict = getattr(settings, "EBIRD_LOCALES")
        loader = APILoader(key, locales)
        species = loader.add_species(species_code)
        messages.add_message(
            self.request,
            messages.INFO,
            "%s was added to the Species list" % species.get_common_name(),
        )


class SpeciesForm(ModelForm):
    common_name = TranslationCharField()
    family_common_name = TranslationCharField(required=False)

    class Meta:
        fields = "__all__"


@admin.register(models.Species)
class SpeciesAdmin(admin.ModelAdmin):
    list_display = (
        "get_common_name",
        "scientific_name",
        "get_family_common_name",
        "family_scientific_name",
        "order",
    )
    ordering = ("order",)
    search_fields = ("common_name", "scientific_name")
    form = SpeciesForm
    formfield_overrides = {
        TextField: {
            "widget": TextInput(attrs={"class": "vTextField"}),
        }
    }
    readonly_fields = ("taxon_order",)
    fields = (
        "common_name",
        "scientific_name",
        "species_code",
        "order",
        "category",
        "family_common_name",
        "family_scientific_name",
        "family_code",
        "data",
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "data":
            field.widget = Textarea(attrs={"rows": 5, "class": "vLargeTextField"})
        return field

    def get_urls(self):
        return [
            path(
                "fetch/",
                self.admin_site.admin_view(FetchSpeciesView.as_view()),
                name="data_species_fetch",
            ),
            *super().get_urls(),
        ]

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["fetch_species_url"] = reverse("admin:data_species_fetch")
        return super().changelist_view(request, extra_context=extra_context)
