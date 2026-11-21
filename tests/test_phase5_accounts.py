from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.alerts.models import Alert, AlertDelivery, SavedSearch
from apps.alerts.tasks import send_due_alerts, send_instant_alerts
from apps.core.models import ApplicantType, Country, Sector
from apps.opportunities.models import Opportunity
from apps.tracker.models import Bookmark, DeadlineReminder, Note, PipelineItem
from apps.tracker.tasks import send_deadline_reminders

User = get_user_model()


def make_opportunity(title: str) -> Opportunity:
    return Opportunity.objects.create(
        title=title,
        opportunity_type=Opportunity.OpportunityType.GRANT,
        official_source_url=f"https://example.org/{title.lower().replace(' ', '-')}",
        status=Opportunity.Status.OPEN,
        date_last_verified=timezone.now(),
        deadline_date=timezone.localdate() + timedelta(days=14),
    )


def make_user(username: str, email: str):
    return User.objects.create_user(
        username=username,
        email=email,
        password="a-strong-test-password-932!",
    )


@pytest.mark.django_db
@override_settings(ACCOUNT_EMAIL_VERIFICATION="none")
def test_email_signup_login_and_private_profile(client) -> None:
    signup = client.post(
        reverse("account_signup"),
        {
            "email": "applicant@example.org",
            "password1": "a-strong-test-password-932!",
            "password2": "a-strong-test-password-932!",
        },
    )

    user = User.objects.get(email="applicant@example.org")
    assert signup.status_code == 302
    assert user.username
    login = client.post(
        reverse("account_login"),
        {"login": "applicant@example.org", "password": "a-strong-test-password-932!"},
    )
    assert login.status_code == 302

    country = Country.objects.create(alpha_2="NG", alpha_3="NGA", name="Nigeria")
    sector = Sector.objects.create(name="Health", slug="health")
    applicant_type = ApplicantType.objects.create(name="NGO", slug="ngo")
    invalid_profile = client.post(
        reverse("accounts:profile"),
        {
            "first_name": "Amina",
            "organization_type": applicant_type.pk,
            "profile_countries": [country.pk],
            "profile_sectors": [sector.pk],
            "budget_min_usd": "25000",
            "budget_max_usd": "5000",
        },
    )
    assert invalid_profile.status_code == 200
    user.refresh_from_db()
    assert user.budget_min_usd is None
    profile = client.post(
        reverse("accounts:profile"),
        {
            "first_name": "Amina",
            "last_name": "Applicant",
            "organization_name": "Community Health Group",
            "organization_type": applicant_type.pk,
            "profile_countries": [country.pk],
            "profile_sectors": [sector.pk],
            "budget_min_usd": "5000",
            "budget_max_usd": "25000",
        },
    )
    user.refresh_from_db()
    assert profile.status_code == 302
    assert user.organization_name == "Community Health Group"
    assert list(user.profile_countries.all()) == [country]
    assert list(user.profile_sectors.all()) == [sector]
    assert user.budget_min_usd == Decimal("5000")


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_email_signup_requires_verification_before_login(client) -> None:
    response = client.post(
        reverse("account_signup"),
        {
            "email": "verify@example.org",
            "password1": "a-strong-test-password-932!",
            "password2": "a-strong-test-password-932!",
        },
    )

    user = User.objects.get(email="verify@example.org")
    assert response.status_code == 302
    address = EmailAddress.objects.get(user=user, email=user.email)
    assert not address.verified
    assert len(mail.outbox) == 1
    assert "Confirm" in mail.outbox[0].subject
    login = client.post(
        reverse("account_login"),
        {"login": user.email, "password": "a-strong-test-password-932!"},
    )
    assert login.status_code == 302
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_saved_search_requires_alert_consent_and_stays_user_scoped(client) -> None:
    user = make_user("applicant", "applicant@example.org")
    client.force_login(user)
    opportunity = make_opportunity("Community health funding")
    save_url = f"{reverse('alerts:save-search')}?q=health"

    no_consent = client.post(
        save_url,
        {
            "name": "Health grants",
            "enable_email_alert": "on",
            "frequency": Alert.Frequency.DAILY,
        },
    )
    assert no_consent.status_code == 302
    assert not SavedSearch.objects.exists()

    response = client.post(
        save_url,
        {
            "name": "Health grants",
            "enable_email_alert": "on",
            "frequency": Alert.Frequency.DAILY,
            "consent": "on",
        },
    )
    saved_search = SavedSearch.objects.get(owner=user)
    alert = Alert.objects.get(saved_search=saved_search)
    assert response.status_code == 302
    assert saved_search.filters["q"] == "health"
    assert alert.consent_given_at is not None
    assert alert.frequency == Alert.Frequency.DAILY

    client.post(
        reverse("alerts:update-alert", kwargs={"pk": alert.pk}),
        {"frequency": Alert.Frequency.WEEKLY},
    )
    alert.refresh_from_db()
    assert not alert.is_active
    assert alert.frequency == Alert.Frequency.WEEKLY
    client.post(
        reverse("alerts:update-alert", kwargs={"pk": alert.pk}),
        {"frequency": Alert.Frequency.INSTANT, "is_active": "on"},
    )
    alert.refresh_from_db()
    assert alert.is_active
    assert alert.frequency == Alert.Frequency.INSTANT

    other_user = make_user("other", "other@example.org")
    other_search = SavedSearch.objects.create(owner=other_user, name="Other")
    delete_response = client.post(reverse("alerts:delete-search", kwargs={"pk": other_search.pk}))
    assert delete_response.status_code == 404
    assert SavedSearch.objects.filter(pk=other_search.pk, owner=other_user).exists()
    assert opportunity.status == Opportunity.Status.OPEN


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_due_email_alert_sends_only_new_matching_public_opportunities() -> None:
    user = make_user("alertuser", "alertuser@example.org")
    saved_search = SavedSearch.objects.create(
        owner=user,
        name="Health",
        query="health",
        filters={"q": "health"},
    )
    alert = Alert.objects.create(
        saved_search=saved_search,
        frequency=Alert.Frequency.DAILY,
        consent_given_at=timezone.now(),
        next_delivery_at=timezone.now() - timedelta(minutes=1),
    )
    matching = make_opportunity("Health support grant")
    make_opportunity("Agriculture support grant")

    assert Alert.objects.filter(
        pk=alert.pk,
        is_active=True,
        channel=Alert.Channel.EMAIL,
        consent_given_at__isnull=False,
        saved_search__is_active=True,
        frequency__in=[Alert.Frequency.DAILY, Alert.Frequency.WEEKLY],
        next_delivery_at__lte=timezone.now(),
    ).exists()
    result = send_due_alerts()
    assert result == 1, list(
        AlertDelivery.objects.values("status", "error_message", "opportunity_ids")
    )
    delivery = AlertDelivery.objects.get(alert=alert)
    assert delivery.status == AlertDelivery.Status.SENT
    assert delivery.opportunity_ids == [matching.pk]
    assert len(mail.outbox) == 1
    assert "Health support grant" in mail.outbox[0].body
    assert matching.official_source_url in mail.outbox[0].body
    assert send_due_alerts() == 0


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_deadline_reminder_requires_opt_in_and_is_idempotent() -> None:
    user = make_user("reminderuser", "reminderuser@example.org")
    user.deadline_reminders_enabled = True
    user.save(update_fields=["deadline_reminders_enabled"])
    opportunity = make_opportunity("Fourteen day deadline grant")
    item = PipelineItem.objects.create(owner=user, opportunity=opportunity)
    unopted_user = make_user("unopted", "unopted@example.org")
    unopted_item = PipelineItem.objects.create(
        owner=unopted_user,
        opportunity=make_opportunity("Unopted deadline grant"),
    )

    assert send_deadline_reminders() == 1
    reminder = DeadlineReminder.objects.get(pipeline_item=item)
    assert reminder.days_before == 14
    assert reminder.status == DeadlineReminder.Status.SENT
    assert len(mail.outbox) == 1
    assert opportunity.official_source_url in mail.outbox[0].body
    assert send_deadline_reminders() == 0
    assert not DeadlineReminder.objects.filter(pipeline_item=unopted_item).exists()


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_instant_alert_sends_for_new_matching_public_opportunity() -> None:
    user = make_user("instantuser", "instantuser@example.org")
    saved_search = SavedSearch.objects.create(
        owner=user,
        name="Health now",
        query="health",
        filters={"q": "health"},
    )
    Alert.objects.create(
        saved_search=saved_search,
        frequency=Alert.Frequency.INSTANT,
        consent_given_at=timezone.now(),
    )
    opportunity = make_opportunity("New health call")

    assert send_instant_alerts(opportunity.pk) == 1
    assert len(mail.outbox) == 1
    assert opportunity.official_source_url in mail.outbox[0].body


@pytest.mark.django_db
def test_instant_alert_is_queued_only_when_an_opportunity_becomes_public() -> None:
    user = make_user("queueuser", "queueuser@example.org")
    saved_search = SavedSearch.objects.create(owner=user, name="All grants")
    Alert.objects.create(
        saved_search=saved_search,
        frequency=Alert.Frequency.INSTANT,
        consent_given_at=timezone.now(),
    )

    with patch("apps.alerts.tasks.send_instant_alerts.delay") as enqueue:
        with patch(
            "apps.alerts.signals.transaction.on_commit",
            side_effect=lambda callback: callback(),
        ):
            opportunity = Opportunity.objects.create(
                title="Unverified grant",
                opportunity_type=Opportunity.OpportunityType.GRANT,
                official_source_url="https://example.org/grant",
                status=Opportunity.Status.UNVERIFIED,
            )
            enqueue.assert_not_called()
            opportunity.status = Opportunity.Status.OPEN
            opportunity.date_last_verified = timezone.now()
            opportunity.save()

    enqueue.assert_called_once_with(opportunity.pk)


@pytest.mark.django_db
def test_bookmarks_pipeline_notes_and_calendar_are_private(client) -> None:
    owner = make_user("owner", "owner@example.org")
    other = make_user("other", "other@example.org")
    client.force_login(owner)
    opportunity = make_opportunity("Private pipeline grant")

    bookmark_response = client.post(
        reverse("tracker:bookmark-toggle", kwargs={"opportunity_id": opportunity.pk}),
        {"action": "save"},
    )
    assert bookmark_response.status_code == 302
    assert Bookmark.objects.filter(owner=owner, opportunity=opportunity).exists()
    assert b"Most saved" in client.get(reverse("search:home")).content

    add_response = client.post(
        reverse("tracker:pipeline-add", kwargs={"opportunity_id": opportunity.pk})
    )
    item = PipelineItem.objects.get(owner=owner, opportunity=opportunity)
    assert add_response.url == reverse("tracker:item-detail", kwargs={"pk": item.pk})
    client.post(
        reverse("tracker:item-detail", kwargs={"pk": item.pk}),
        {"action": "status", "status": PipelineItem.Status.SUBMITTED, "submitted_at": ""},
    )
    item.refresh_from_db()
    assert item.submitted_at is not None
    client.post(
        reverse("tracker:item-detail", kwargs={"pk": item.pk}),
        {"action": "note", "content": "Call the programme officer next week."},
    )
    assert Note.objects.filter(pipeline_item=item, author=owner).exists()

    other_item = PipelineItem.objects.create(
        owner=other, opportunity=make_opportunity("Other grant")
    )
    calendar = client.get(reverse("tracker:calendar-ics"))
    assert calendar.status_code == 200
    assert calendar["Content-Type"].startswith("text/calendar")
    assert b"Private pipeline grant" in calendar.content
    assert b"Other grant" not in calendar.content

    client.force_login(other)
    assert client.get(reverse("tracker:item-detail", kwargs={"pk": item.pk})).status_code == 404
    assert (
        client.get(reverse("tracker:item-detail", kwargs={"pk": other_item.pk})).status_code == 200
    )


@pytest.mark.django_db
def test_personal_pages_require_authentication(client) -> None:
    response = client.get(reverse("tracker:dashboard"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("account_login"))


@pytest.mark.django_db
def test_tracker_recommendations_rank_profile_and_behavior_matches(client) -> None:
    user = make_user("matchinguser", "matchinguser@example.org")
    profile_sector = Sector.objects.create(name="Health", slug="health")
    bookmark_sector = Sector.objects.create(name="Agriculture", slug="agriculture")
    pipeline_sector = Sector.objects.create(name="Education", slug="education")
    country = Country.objects.create(alpha_2="NG", alpha_3="NGA", name="Nigeria")
    user.profile_sectors.add(profile_sector)
    user.profile_countries.add(country)
    user.budget_min_usd = Decimal("1000")
    user.budget_max_usd = Decimal("10000")
    user.save()

    profile_match = make_opportunity("Health opportunity")
    profile_match.amount_usd = Decimal("5000")
    profile_match.save(update_fields=["amount_usd"])
    profile_match.sectors.add(profile_sector)
    profile_match.eligible_countries.add(country)

    bookmarked_source = make_opportunity("Previous agriculture opportunity")
    bookmarked_source.sectors.add(bookmark_sector)
    Bookmark.objects.create(owner=user, opportunity=bookmarked_source)
    bookmark_match = make_opportunity("Agriculture opportunity")
    bookmark_match.amount_usd = Decimal("5000")
    bookmark_match.save(update_fields=["amount_usd"])
    bookmark_match.sectors.add(bookmark_sector)
    bookmark_match.eligible_countries.add(country)

    pipeline_source = make_opportunity("Previous education opportunity")
    pipeline_source.sectors.add(pipeline_sector)
    PipelineItem.objects.create(owner=user, opportunity=pipeline_source)
    pipeline_match = make_opportunity("Education opportunity")
    pipeline_match.amount_usd = Decimal("5000")
    pipeline_match.save(update_fields=["amount_usd"])
    pipeline_match.sectors.add(pipeline_sector)
    pipeline_match.eligible_countries.add(country)

    saved_match = make_opportunity("Already bookmarked health opportunity")
    saved_match.sectors.add(profile_sector)
    Bookmark.objects.create(owner=user, opportunity=saved_match)
    tracked_match = make_opportunity("Already tracked health opportunity")
    tracked_match.sectors.add(profile_sector)
    PipelineItem.objects.create(owner=user, opportunity=tracked_match)

    client.force_login(user)
    response = client.get(reverse("tracker:dashboard"))

    recommendations = response.context["recommendations"]
    recommended_opportunities = [item.opportunity for item in recommendations]
    assert recommended_opportunities[0] == profile_match
    assert set(recommended_opportunities[1:]) == {bookmark_match, pipeline_match}
    assert saved_match not in recommended_opportunities
    assert tracked_match not in recommended_opportunities
    assert b"Best matches" in response.content


@pytest.mark.django_db
def test_calendar_export_escapes_user_controlled_ical_text(client) -> None:
    user = make_user("calendaruser", "calendaruser@example.org")
    client.force_login(user)
    opportunity = make_opportunity("Grant, round; one\r\nBEGIN:VEVENT")
    PipelineItem.objects.create(owner=user, opportunity=opportunity)

    response = client.get(reverse("tracker:calendar-ics"))

    assert b"SUMMARY:Grant\\, round\\; one\\nBEGIN:VEVENT" in response.content
    assert response.content.count(b"\r\nBEGIN:VEVENT\r\n") == 1
