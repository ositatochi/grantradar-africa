from __future__ import annotations

from typing import Any

from django import forms

from apps.alerts.models import Alert


class SaveSearchForm(forms.Form):
    name = forms.CharField(label="Search name", max_length=160)
    enable_email_alert = forms.BooleanField(
        label="Email me when new matching opportunities are found",
        required=False,
    )
    frequency = forms.ChoiceField(
        label="Email frequency",
        choices=[
            (Alert.Frequency.INSTANT, "As soon as a match is found"),
            (Alert.Frequency.DAILY, "Daily"),
            (Alert.Frequency.WEEKLY, "Weekly"),
        ],
        initial=Alert.Frequency.DAILY,
    )
    consent = forms.BooleanField(
        label="I agree to receive email alerts for this saved search.",
        required=False,
    )

    def clean_name(self) -> str:
        value = self.cleaned_data.get("name")
        if not isinstance(value, str):
            return ""
        name = value
        if "\r" in name or "\n" in name:
            raise forms.ValidationError("Search names cannot contain line breaks.")
        return name

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return {}
        if cleaned_data.get("enable_email_alert") and not cleaned_data.get("consent"):
            self.add_error("consent", "Consent is required to enable email alerts.")
        return cleaned_data


class AlertSettingsForm(forms.Form):
    frequency = forms.ChoiceField(
        choices=[
            (Alert.Frequency.INSTANT, "As soon as a match is found"),
            (Alert.Frequency.DAILY, "Daily"),
            (Alert.Frequency.WEEKLY, "Weekly"),
        ]
    )
    is_active = forms.BooleanField(required=False)
    consent = forms.BooleanField(required=False)

    def __init__(self, *args: Any, has_consent: bool, **kwargs: Any) -> None:
        self.has_consent = has_consent
        super().__init__(*args, **kwargs)

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return {}
        if cleaned_data.get("is_active") and not (self.has_consent or cleaned_data.get("consent")):
            self.add_error("consent", "Consent is required to enable email alerts.")
        return cleaned_data
