"""
repair_observers.py

A Django management command for repairing checklists assigned to an
Observer by mistake.

Usage:
    python manage.py repair_observers [--identifier <identifier>] [--dry-run]

Arguments:
    --identifier <identifier> The identifier of the Observer to repair. If
        not given then it defaults to the empty string.

    --dry-run Show what would be changed, without changing the database.

Examples:
    # Repair the checklists assigned to the Observer with an empty identifier
    python manage.py repair_observers

    # Show which observers the checklists would be assigned to
    python manage.py repair_observers --dry-run

Notes:
    1. Up to version 0.5.2, the loader scraped the checklist web page to get
       the observer's eBird user id. Since eBird started blocking bots, the
       identifier scraped was always empty, so every new observer was saved
       to the same Observer record, with an empty identifier. The record was
       renamed each time a new observer was added.

    2. To repair the checklists, the name of each observer is fetched from the
       list of visits for the checklist's state, on the date of the checklist.
       That takes far fewer calls to the eBird API than fetching each checklist.
       If the checklist cannot be found then it is fetched directly. The
       observer is then found, or added, in the same way as when the checklist
       is loaded, and the checklist and its observations are reassigned.

    3. Once all the checklists have been reassigned, the Observer record is
       deleted. If any checklists could not be repaired, e.g. they were deleted
       from eBird, then they remain assigned to the Observer, and the command
       can be run again.

"""

import datetime as dt
import logging

from urllib.error import HTTPError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ebird.api.requests import get_checklist

from ebird.api.data.loaders import APILoader
from ebird.api.data.models import Checklist, Observer

logger = logging.getLogger(__name__)

# The name given to the Observer being repaired, so the loader does not
# assign checklists to it when looking up observers by name.
REPAIR_NAME = "Observer being repaired"


class Command(BaseCommand):
    help = "Reassign checklists assigned to an Observer by mistake"

    def add_arguments(self, parser):
        parser.add_argument(
            "--identifier",
            type=str,
            default="",
            help="The identifier of the Observer to repair. Defaults to ''.",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be changed, without changing the database.",
        )

    @staticmethod
    def get_loader() -> APILoader:
        key: str = settings.EBIRD_API_KEY
        locales: dict = settings.EBIRD_LOCALES
        rate_limit: float | None = getattr(settings, "EBIRD_RATE_LIMIT", None)
        return APILoader(key, locales, rate_limit=rate_limit)

    @staticmethod
    def get_names(loader: APILoader, region: str, date: dt.date) -> dict[str, str]:
        visits: list[dict] = loader.fetch_visits(region, date)
        return {
            visit["subId"]: visit.get("userDisplayName", "Anonymous eBirder")
            for visit in visits
        }

    @staticmethod
    def get_name(loader: APILoader, identifier: str) -> str | None:
        try:
            data: dict = loader.call_api(get_checklist, identifier)
        except HTTPError as err:
            logger.warning("Checklist %s: could not be fetched, %s", identifier, err)
            return None
        return data.get("userDisplayName", "Anonymous eBirder")

    def handle(self, *args, **options):
        identifier: str = options["identifier"]
        dry_run: bool = options["dry_run"]

        merged: Observer | None = Observer.objects.filter(identifier=identifier).first()

        if merged is None:
            raise CommandError("Observer '%s' does not exist" % identifier)

        checklists = (
            Checklist.objects.filter(observer=merged)
            .select_related("state", "location")
            .order_by("date", "identifier")
        )

        logger.info(
            "Observer '%s' (%s): %d checklists to repair",
            identifier,
            merged.name,
            checklists.count(),
        )

        loader: APILoader = self.get_loader()
        names: dict[tuple, dict[str, str]] = {}
        repaired: int = 0
        skipped: int = 0

        with transaction.atomic():
            # Rename the Observer so the loader does not match it by name.
            merged.name = REPAIR_NAME
            merged.original = REPAIR_NAME
            merged.save()

            for checklist in checklists:
                key = (checklist.state.code, checklist.date)
                if key not in names:
                    names[key] = self.get_names(loader, *key)

                name = names[key].get(checklist.identifier)
                if name is None:
                    name = self.get_name(loader, checklist.identifier)

                if name is None:
                    skipped += 1
                    continue

                data: dict = {
                    "subId": checklist.identifier,
                    "userDisplayName": name,
                    "locId": checklist.location.identifier,
                    "obsDt": checklist.started.strftime("%Y-%m-%d %H:%M"),
                }

                observer: Observer = loader.get_observer(data)

                if observer.pk == merged.pk:
                    skipped += 1
                    continue

                checklist.observer = observer
                checklist.save()
                checklist.observations.update(observer=observer)
                repaired += 1

                logger.info(
                    "Checklist %s: assigned to %s (%s)",
                    checklist.identifier,
                    observer.name,
                    observer.identifier,
                )

            if not merged.checklists.exists() and not merged.observations.exists():
                merged.delete()
                logger.info("Observer '%s': deleted", identifier)

            logger.info("Repaired %d checklists, skipped %d", repaired, skipped)

            if dry_run:
                transaction.set_rollback(True)
                logger.info("Dry run: no changes were saved")
