from __future__ import annotations

from typing import Any

from django import forms

from apps.core.models import ApplicantType, Country, Currency, Sector, Theme
from apps.funders.models import Funder
from apps.opportunities.models import Opportunity


class OpportunitySearchForm(forms.Form):
    q = forms.CharField(label="Search", required=False, max_length=200)
    country = forms.ModelChoiceField(
        label="Eligible country",
        queryset=Country.objects.none(),
        required=False,
    )
    region = forms.ChoiceField(label="Region", required=False)
    sector = forms.ModelChoiceField(
        label="Sector",
        queryset=Sector.objects.none(),
        required=False,
    )
    theme = forms.ModelChoiceField(
        label="Theme",
        queryset=Theme.objects.none(),
        required=False,
    )
    funder = forms.ModelChoiceField(
        label="Funder",
        queryset=Funder.objects.none(),
        required=False,
    )
    funder_type = forms.ChoiceField(label="Funder type", required=False)
    opportunity_type = forms.ChoiceField(label="Opportunity type", required=False)
    applicant_type = forms.ModelChoiceField(
        label="Applicant type",
        queryset=ApplicantType.objects.none(),
        required=False,
    )
    currency = forms.ModelChoiceField(
        label="Currency",
        queryset=Currency.objects.none(),
        required=False,
    )
    language = forms.ChoiceField(
        label="Language",
        choices=[
            ("", "Any language"),
            ("en", "English"),
            ("fr", "French"),
            ("pt", "Portuguese"),
            ("ar", "Arabic"),
        ],
        required=False,
    )
    status = forms.ChoiceField(label="Status", required=False)
    min_amount_usd = forms.DecimalField(
        label="Minimum amount (USD)",
        required=False,
        min_value=0,
        max_digits=16,
        decimal_places=2,
    )
    max_amount_usd = forms.DecimalField(
        label="Maximum amount (USD)",
        required=False,
        min_value=0,
        max_digits=16,
        decimal_places=2,
    )
    deadline_after = forms.DateField(
        label="Deadline from",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    deadline_before = forms.DateField(
        label="Deadline to",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    no_match = forms.BooleanField(label="No matching funds required", required=False)
    individuals_allowed = forms.BooleanField(
        label="Individuals allowed",
        required=False,
    )
    sort = forms.ChoiceField(
        label="Sort by",
        choices=[
            ("relevance", "Relevance"),
            ("deadline", "Deadline"),
            ("newest", "Newest"),
            ("amount", "Amount (USD)"),
        ],
        required=False,
        initial="relevance",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["country"] = forms.ModelChoiceField(
            label="Eligible country",
            queryset=Country.objects.order_by("name"),
            required=False,
        )
        self.fields["sector"] = forms.ModelChoiceField(
            label="Sector",
            queryset=Sector.objects.filter(is_active=True),
            required=False,
        )
        self.fields["theme"] = forms.ModelChoiceField(
            label="Theme",
            queryset=Theme.objects.filter(is_active=True),
            required=False,
        )
        self.fields["funder"] = forms.ModelChoiceField(
            label="Funder",
            queryset=Funder.objects.filter(is_active=True),
            required=False,
        )
        self.fields["applicant_type"] = forms.ModelChoiceField(
            label="Applicant type",
            queryset=ApplicantType.objects.filter(is_active=True),
            required=False,
        )
        self.fields["currency"] = forms.ModelChoiceField(
            label="Currency",
            queryset=Currency.objects.filter(is_active=True),
            required=False,
        )
        regions = Country.objects.exclude(region="").values_list("region", flat=True).distinct()
        self.fields["region"] = forms.ChoiceField(
            label="Region",
            choices=[("", "Any region"), *((region, region) for region in regions)],
            required=False,
        )
        self.fields["funder_type"] = forms.ChoiceField(
            label="Funder type",
            choices=[("", "Any funder type"), *Funder.FunderType.choices],
            required=False,
        )
        self.fields["opportunity_type"] = forms.ChoiceField(
            label="Opportunity type",
            choices=[("", "Any opportunity type"), *Opportunity.OpportunityType.choices],
            required=False,
        )
        self.fields["status"] = forms.ChoiceField(
            label="Status",
            choices=[
                ("", "Any status"),
                *(
                    choice
                    for choice in Opportunity.Status.choices
                    if choice[0] != Opportunity.Status.UNVERIFIED
                ),
            ],
            required=False,
        )

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return {}
        minimum = cleaned_data.get("min_amount_usd")
        maximum = cleaned_data.get("max_amount_usd")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("max_amount_usd", "Maximum amount must be at least the minimum.")
        start = cleaned_data.get("deadline_after")
        end = cleaned_data.get("deadline_before")
        if start is not None and end is not None and start > end:
            self.add_error("deadline_before", "The end date must be on or after the start date.")
        return cleaned_data
