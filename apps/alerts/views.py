from __future__ import annotations

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.alerts.forms import AlertSettingsForm, SaveSearchForm
from apps.alerts.models import Alert, SavedSearch
from apps.alerts.services import display_filters, next_delivery_time, normalize_search_filters


@login_required
@require_POST
def save_search(request: HttpRequest) -> HttpResponse:
    user_id = _authenticated_user_id(request)
    form = SaveSearchForm(request.POST)
    try:
        filters = normalize_search_filters(request.GET)
    except ValueError:
        messages.error(request, "Correct the search filters before saving this search.")
        return redirect("search:opportunity-list")

    if not form.is_valid():
        messages.error(request, "Review the saved-search name and email alert consent.")
        return _search_results_redirect(request)

    name = form.cleaned_data["name"]
    if SavedSearch.objects.filter(owner_id=user_id, name=name).exists():
        messages.error(request, "You already have a saved search with this name.")
        return _search_results_redirect(request)

    try:
        with transaction.atomic():
            saved_search = SavedSearch.objects.create(
                owner_id=user_id,
                name=name,
                query=filters.get("q", ""),
                filters=filters,
            )
            if form.cleaned_data["enable_email_alert"]:
                now = timezone.now()
                frequency = form.cleaned_data["frequency"]
                Alert.objects.create(
                    saved_search=saved_search,
                    frequency=frequency,
                    channel=Alert.Channel.EMAIL,
                    consent_given_at=now,
                    next_delivery_at=next_delivery_time(frequency, now),
                )
    except IntegrityError:
        messages.error(request, "A saved search with that name already exists.")
        return _search_results_redirect(request)

    messages.success(request, f"Saved search “{saved_search.name}”.")
    return redirect("alerts:saved-searches")


@login_required
def saved_searches(request: HttpRequest) -> HttpResponse:
    user_id = _authenticated_user_id(request)
    searches = SavedSearch.objects.filter(owner_id=user_id).prefetch_related("alerts")
    entries = [
        {
            "saved_search": saved_search,
            "filters": display_filters(saved_search),
            "query_string": urlencode(display_filters(saved_search)),
        }
        for saved_search in searches
    ]
    return render(request, "alerts/saved_searches.html", {"entries": entries})


@login_required
@require_POST
def update_alert(request: HttpRequest, pk: int) -> HttpResponse:
    user_id = _authenticated_user_id(request)
    alert = get_object_or_404(
        Alert.objects.select_related("saved_search"),
        pk=pk,
        saved_search__owner_id=user_id,
    )
    form = AlertSettingsForm(request.POST, has_consent=alert.consent_given_at is not None)
    if not form.is_valid():
        messages.error(request, "Review the alert frequency and email consent.")
        return redirect("alerts:saved-searches")

    if form.cleaned_data["consent"] and alert.consent_given_at is None:
        alert.consent_given_at = timezone.now()
    alert.frequency = form.cleaned_data["frequency"]
    alert.is_active = form.cleaned_data["is_active"]
    alert.next_delivery_at = next_delivery_time(alert.frequency) if alert.is_active else None
    alert.save(
        update_fields=[
            "consent_given_at",
            "frequency",
            "is_active",
            "next_delivery_at",
            "updated_at",
        ]
    )
    messages.success(request, "Email alert settings updated.")
    return redirect("alerts:saved-searches")


@login_required
@require_POST
def delete_saved_search(request: HttpRequest, pk: int) -> HttpResponse:
    user_id = _authenticated_user_id(request)
    saved_search = get_object_or_404(SavedSearch, pk=pk, owner_id=user_id)
    saved_search.delete()
    messages.success(request, "Saved search removed.")
    return redirect("alerts:saved-searches")


def _search_results_redirect(request: HttpRequest) -> HttpResponse:
    query_string = request.GET.urlencode()
    url = reverse("search:opportunity-list")
    return redirect(f"{url}?{query_string}" if query_string else url)


def _authenticated_user_id(request: HttpRequest) -> int:
    user_id = request.user.pk
    if user_id is None:
        raise PermissionDenied
    return user_id
