"""
load_api.py

A Django management command for loading observations from the eBird API.

Usage:
    python manage.py add_checklists --date <date> <region>+
    python manage.py add_checklists --days <n> <region>+
    python manage.py add_checklists --date <date> --days <n> <region>+

Arguments:
    --date <date> The date of the checklists to add to the database. If
        no date is given then it defaults to today.

    --days <n> The number of days to include. If not given then the number
        of days defaults to 1. That means only checklists for the date will
        be added.

    <region> Required. One or more national, subnational1, subnational2, or hotspot
        codes used by eBird. For example, US, US-NY, US-NY-109, L1379126

Examples:
    # Load checklists added in the past week for New York state
    python manage.py add_checklists --days 7 US-NY

    # Load checklists all checklists added on the last Big Day
    python manage.py add_checklists --date 2024-10-05 US-NY

Notes:
    1. The eBird API returns a maximum of 200 results. The APILoader works
       around this by fetching checklists from sub-regions if necessary.
       Downloading checklists once a day should be sufficient for all hotspots
       or subnational2 areas. For large countries or places with lots of birders
       downloads will have to be more frequent. For really large area, i.e. the
       USA you shouldn't be using the API at all. Instead use the data from the
       eBird Basic Dataset.

    2. Why does the command only add checklists, not update existing ones?
       The number of checklists that are updated is relatively small, typically
       less than 1%. The problem with the eBird API is that you can only find
       out whether a checklist has changed by downloading it. This app basically
       mirrors the eBird database for a given region so there's a strong temptation
       to repeatedly download everything to keep the checklists in sync. That
       means repeatedly downloading all the checklists submitted in the past week
       or month, or longer to pick up a few changes. That's a heavy load on the
       eBird servers and a lot of bandwidth for relatively little gain.

       The API is really a news service. For accuracy and completeness you should
       really use the eBird Basic Dataset, which is published on the 15th of each
       month.

    3. The API has limitations. Observers are only identified by name. So if there
       are two Juan Garcias birding in a region, then all the observations will
       appear to belong to one person. To work around this, when an observer is
       added the web page for the checklist is scraped to extract their eBird
       user id.

       Also the observations will not have been reviewed by moderators, so there
       are likely to be records where the identification is incorrect.

    4. You automate running the command using a scheduler such as cron. If you use
       the absolute paths to python and the command, then you don't need to deal
       with activating the virtual environment, for example:

       # Just before midnight, add all checklists submitted for the past week
       55 23 * * * /home/me/my-project/.venv/bin/python /home/me/my-project/manage.py add_checklists --days 7 US-NY

"""

import datetime as dt

from django.conf import settings
from django.core.management.base import BaseCommand

from ebird.api.data.loaders import APILoader


class Command(BaseCommand):
    help = "Add checklists from the eBird API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=lambda s: dt.datetime.strptime(s, "%Y-%m-%d"),
            help="The number of previous days to add",
        )

        parser.add_argument(
            "--days",
            type=int,
            help="The number of previous days to add",
        )

        parser.add_argument(
            "regions",
            nargs="+",
            type=str,
            help="Codes for the eBird regions, e.g US-NY",
        )

    @staticmethod
    def get_loader() -> APILoader:
        key: str = getattr(settings, "EBIRD_API_KEY")
        locales: dict = getattr(settings, "EBIRD_LOCALES")
        return APILoader(key, locales)

    @staticmethod
    def get_dates(days) -> list[dt.date]:
        today: dt.date = dt.date.today()
        return [today - dt.timedelta(days=n) for n in range(days)]

    def handle(self, *args, **options):
        date = options["date"] or dt.date.today()
        days = options["days"] or 1

        dates = [date - dt.timedelta(days=n) for n in range(days)]
        loader = self.get_loader()

        for region in options["regions"]:
            for date in dates:
                loader.add_checklists(region, date)
