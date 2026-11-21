from typing import Any

import pycountry
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import (
    ApplicantType,
    Country,
    Currency,
    Sector,
    SustainableDevelopmentGoal,
    Theme,
)
from apps.core.reference_data import (
    AFRICA_COUNTRY_CODES,
    APPLICANT_TYPES,
    SDG_GOALS,
    SECTORS,
    THEMES,
)


class Command(BaseCommand):
    help = "Load countries, currencies, SDGs, sectors, themes, and applicant types."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        for number, title in SDG_GOALS:
            SustainableDevelopmentGoal.objects.update_or_create(
                number=number,
                defaults={"title": title},
            )

        goals = {goal.number: goal for goal in SustainableDevelopmentGoal.objects.all()}
        for name, slug, goal_number in SECTORS:
            Sector.objects.update_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "sdg_goal": goals[goal_number],
                    "is_active": True,
                },
            )

        for name, slug in THEMES:
            Theme.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "is_active": True},
            )

        for name, slug in APPLICANT_TYPES:
            ApplicantType.objects.update_or_create(
                slug=slug,
                defaults={"name": name, "is_active": True},
            )

        countries = [
            Country(
                alpha_2=country.alpha_2,
                alpha_3=country.alpha_3,
                name=country.name,
                region="Africa" if country.alpha_2 in AFRICA_COUNTRY_CODES else "",
            )
            for country in pycountry.countries
        ]
        Country.objects.bulk_create(
            countries,
            update_conflicts=True,
            unique_fields=["alpha_2"],
            update_fields=["alpha_3", "name", "region"],
        )

        currencies = [
            Currency(
                code=currency.alpha_3,
                name=currency.name,
                numeric_code=getattr(currency, "numeric", ""),
                is_active=not hasattr(currency, "withdrawal_date"),
            )
            for currency in pycountry.currencies
        ]
        Currency.objects.bulk_create(
            currencies,
            update_conflicts=True,
            unique_fields=["code"],
            update_fields=["name", "numeric_code", "is_active"],
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Loaded "
                f"{Country.objects.count()} countries, "
                f"{Currency.objects.count()} currencies, "
                f"{SustainableDevelopmentGoal.objects.count()} SDGs, "
                f"{Sector.objects.count()} sectors, "
                f"{Theme.objects.count()} themes, and "
                f"{ApplicantType.objects.count()} applicant types."
            )
        )
