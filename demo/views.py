from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber
from django.forms.widgets import Media
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import translation
from django.utils.translation import gettext_lazy as _
from django.views import generic
from django.views.generic.base import ContextMixin

from ebird.api.data.models import Checklist, Observation, Species

from .forms import (
    CategoryFilter,
    DateRangeFilter,
    LocationFilter,
    ObserverFilter,
    SpeciesFilter,
)


class FormsMixin(ContextMixin):
    """Provide a way to show and handle multiple form in a request."""

    form_classes = []
    initial = {}
    extra = {}
    methods = []
    prefixes = {}
    success_url = None

    def __init__(self):
        self.object_list = None

    def get_initial(self, identifier):
        """Return the initial data to use for forms on this view."""
        return self.initial.get(identifier, {}).copy()

    def get_methods(self):
        return self.methods

    def get_prefix(self, identifier):
        """Return the prefixes to use for forms."""
        return self.prefixes.get(identifier)

    def get_forms(self):
        """Return set of form sto be used in this view."""
        forms = {}
        for form_class in self.form_classes:
            identifier = form_class.form_id
            forms[identifier] = form_class(**self.get_form_kwargs(identifier))
        return forms

    def get_media(self, forms):
        media = Media()
        for form in forms.values():
            media += form.media
        return media

    def get_extra_kwargs(self, identifier):
        return self.extra.get(identifier, {})

    def get_form_kwargs(self, identifier):
        """Return the keyword arguments for instantiating the form."""
        kwargs = {
            "initial": self.get_initial(identifier),
            "prefix": self.get_prefix(identifier),
        }

        kwargs.update(self.get_extra_kwargs(identifier))

        request = getattr(self, "request")

        if request.method in self.get_methods():
            kwargs.update(
                {
                    "data": getattr(request, request.method),
                    "files": request.FILES,
                }
            )
        return kwargs

    def get_success_url(self):
        """Return the URL to redirect to after processing a valid form."""
        if not self.success_url:
            raise ImproperlyConfigured("No URL to redirect to. Provide a success_url.")
        return str(self.success_url)  # success_url may be lazy

    def forms_valid(self, forms, **kwargs):
        return HttpResponseRedirect(self.get_success_url())

    def forms_invalid(self, forms, **kwargs):
        return self.render_to_response(self.get_context_data(forms=forms, **kwargs))

    def get_context_data(self, **kwargs):
        """Insert the form into the context dict."""
        if "forms" not in kwargs:
            kwargs["forms"] = self.get_forms()
        kwargs["media"] = self.get_media(kwargs["forms"])
        return super().get_context_data(**kwargs)


class FilteredListView(FormsMixin, generic.ListView):
    default_filters = None
    default_order = None
    related = None
    methods = ["GET"]

    def get_default_filters(self):
        return self.default_filters or {}

    def get_related(self):
        return self.related

    def get_default_order(self):
        return self.default_order or []

    def get_order(self, forms):
        order = self.get_default_order()
        for identifier, form in forms.items():
            order.extend(form.get_ordering())
        return order

    def get_filters(self, forms):
        filters = self.get_default_filters()
        for identifier, form in forms.items():
            filters.update(form.get_filters())
        return filters

    def get_filtered_queryset(self, forms):
        self.ordering = self.get_order(forms)
        queryset = super().get_queryset()
        queryset = queryset.filter(**self.get_filters(forms))
        queryset = queryset.select_related(*self.get_related())
        return queryset

    def forms_invalid(self, forms, **kwargs):
        self.object_list = self.get_filtered_queryset(forms)
        return super().forms_invalid(forms=forms)

    def handle_request(self, request, *args, **kwargs):
        forms = self.get_forms()
        [form.is_valid() for identifier, form in forms.items()]
        return self.forms_invalid(forms)

    def get(self, request, *args, **kwargs):
        return self.handle_request(request, *args, **kwargs)


class ChecklistsView(FilteredListView):
    default_filter = Q(published=True)
    form_classes = [
        LocationFilter,
        ObserverFilter,
        DateRangeFilter,
    ]
    model = Checklist
    paginate_by = 50
    template_name = "checklists/list.html"
    url = "checklists"

    def get_url(self):
        return reverse(self.url)

    def get_related(self):  # noqa
        return ["country", "state", "county", "location", "observer"]

    def get_translated_urls(self):
        urls = []
        for code, name in settings.LANGUAGES:
            with translation.override(code):
                urls.append((self.get_url(), name))
        return urls

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["translations"] = self.get_translated_urls()
        return context


class ObservationsView(FilteredListView):
    default_filter = Q(published=True)
    form_classes = (
        LocationFilter,
        ObserverFilter,
        DateRangeFilter,
        SpeciesFilter,
    )
    model = Observation
    template_name = "observations/list.html"
    paginate_by = 100
    url = "observations"

    def get_url(self):
        return reverse(self.url)

    def get_related(self):  # noqa
        return ["country", "state", "county", "location", "observer", "species"]

    def get_translated_urls(self):
        urls = []
        for code, name in settings.LANGUAGES:
            with translation.override(code):
                urls.append((self.get_url(), name))
        return urls

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["translations"] = self.get_translated_urls()
        return context


class SpeciesView(FilteredListView):
    default_filter = Q(published=True)
    form_classes = (
        LocationFilter,
        ObserverFilter,
        DateRangeFilter,
        CategoryFilter,
    )
    model = Observation
    template_name = "species/list.html"
    url = "species"

    def get_url(self):
        return reverse(self.url)

    def get_related(self):  # noqa
        return [
            "checklist",
            "country",
            "state",
            "county",
            "location",
            "observer",
            "species",
        ]

    def get_filtered_queryset(self, forms):
        # Select the first observation of each species. A window function is
        # used, instead of distinct("species"), since DISTINCT ON is only
        # supported by PostgreSQL.
        first_seen = Window(
            RowNumber(),
            partition_by=F("species"),
            order_by=[F("started").asc(), F("pk").asc()],
        )
        queryset = super().get_filtered_queryset(forms)
        return queryset.annotate(row_number=first_seen).filter(row_number=1)

    def get_translated_urls(self):
        urls = []
        for code, name in settings.LANGUAGES:
            with translation.override(code):
                urls.append((self.get_url(), name))
        return urls

    def get_category_title(self):
        if category := self.request.GET.get("category"):
            title = Species.Category[category].label
        else:
            title = _("Species, Forms, etc.")
        return title

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["translations"] = self.get_translated_urls()
        context["category_title"] = self.get_category_title()
        context["species_list"] = sorted(
            list(context["object_list"]), key=lambda obj: obj.species.taxon_order
        )
        return context
