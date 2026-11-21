from __future__ import annotations

from typing import Any

from django import forms

from apps.accounts.models import User
from apps.core.models import ApplicantType, Country, Sector


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "organization_name",
            "organization_type",
            "profile_countries",
            "profile_sectors",
            "budget_min_usd",
            "budget_max_usd",
            "deadline_reminders_enabled",
        ]
        widgets = {
            "profile_countries": forms.SelectMultiple(attrs={"size": 6}),
            "profile_sectors": forms.SelectMultiple(attrs={"size": 6}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["organization_type"] = forms.ModelChoiceField(
            queryset=ApplicantType.objects.filter(is_active=True),
            required=False,
        )
        self.fields["profile_countries"] = forms.ModelMultipleChoiceField(
            queryset=Country.objects.order_by("name"),
            required=False,
            widget=forms.SelectMultiple(attrs={"size": 6}),
        )
        self.fields["profile_sectors"] = forms.ModelMultipleChoiceField(
            queryset=Sector.objects.filter(is_active=True),
            required=False,
            widget=forms.SelectMultiple(attrs={"size": 6}),
        )

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return {}
        minimum = cleaned_data.get("budget_min_usd")
        maximum = cleaned_data.get("budget_max_usd")
        if minimum is not None and maximum is not None and minimum > maximum:
            self.add_error("budget_max_usd", "Maximum budget must be at least the minimum.")
        return cleaned_data
