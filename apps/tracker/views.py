from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.search.recommendations import recommendations_for
from apps.search.services import public_opportunities
from apps.tracker.forms import NoteForm, PipelineItemForm
from apps.tracker.models import Bookmark, PipelineItem


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    if not isinstance(request.user, User):
        raise PermissionDenied("Sign in to view your funding tracker.")
    bookmarks = Bookmark.objects.filter(
        owner_id=request.user.pk, opportunity__in=public_opportunities()
    ).select_related("opportunity", "opportunity__funder")
    pipeline_items = PipelineItem.objects.filter(owner_id=request.user.pk).select_related(
        "opportunity", "opportunity__funder"
    )
    recommendations = recommendations_for(request.user)
    return render(
        request,
        "tracker/dashboard.html",
        {
            "bookmarks": bookmarks,
            "pipeline_items": pipeline_items,
            "recommendations": recommendations,
        },
    )


@login_required
@require_POST
def toggle_bookmark(request: HttpRequest, opportunity_id: int) -> HttpResponse:
    opportunity = get_object_or_404(public_opportunities(), pk=opportunity_id)
    action = request.POST.get("action")
    if action == "remove":
        Bookmark.objects.filter(owner_id=request.user.pk, opportunity=opportunity).delete()
        messages.success(request, "Opportunity removed from your bookmarks.")
    elif action == "save":
        Bookmark.objects.get_or_create(owner_id=request.user.pk, opportunity=opportunity)
        messages.success(request, "Opportunity saved to your bookmarks.")
    else:
        return HttpResponseBadRequest("Choose whether to save or remove this bookmark.")
    return redirect(opportunity.get_absolute_url())


@login_required
@require_POST
def add_to_pipeline(request: HttpRequest, opportunity_id: int) -> HttpResponse:
    opportunity = get_object_or_404(public_opportunities(), pk=opportunity_id)
    item, created = PipelineItem.objects.get_or_create(
        owner_id=request.user.pk,
        opportunity=opportunity,
    )
    if created:
        messages.success(request, "Opportunity added to your application tracker.")
    else:
        messages.info(request, "This opportunity is already in your tracker.")
    return redirect("tracker:item-detail", pk=item.pk)


@login_required
def item_detail(request: HttpRequest, pk: int) -> HttpResponse:
    item = get_object_or_404(
        PipelineItem.objects.select_related("opportunity"),
        pk=pk,
        owner_id=request.user.pk,
    )
    status_form = PipelineItemForm(instance=item)
    note_form = NoteForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "status":
            status_form = PipelineItemForm(request.POST, instance=item)
            if status_form.is_valid():
                updated_item = status_form.save(commit=False)
                if (
                    updated_item.status == PipelineItem.Status.SUBMITTED
                    and updated_item.submitted_at is None
                ):
                    updated_item.submitted_at = timezone.now()
                updated_item.save()
                messages.success(request, "Tracker status updated.")
                return redirect("tracker:item-detail", pk=item.pk)
        elif action == "note":
            note_form = NoteForm(request.POST)
            if note_form.is_valid():
                note = note_form.save(commit=False)
                note.pipeline_item = item
                note.author_id = request.user.pk
                note.save()
                messages.success(request, "Private note added.")
                return redirect("tracker:item-detail", pk=item.pk)
        else:
            return HttpResponseBadRequest("Choose a tracker action.")

    return render(
        request,
        "tracker/item_detail.html",
        {
            "item": item,
            "status_form": status_form,
            "note_form": note_form,
            "notes": item.notes.select_related("author"),
        },
    )


@login_required
@require_POST
def remove_from_pipeline(request: HttpRequest, pk: int) -> HttpResponse:
    item = get_object_or_404(PipelineItem, pk=pk, owner_id=request.user.pk)
    item.delete()
    messages.success(request, "Opportunity removed from your tracker.")
    return redirect("tracker:dashboard")


@login_required
def calendar_ics(request: HttpRequest) -> HttpResponse:
    items = (
        PipelineItem.objects.filter(
            owner_id=request.user.pk,
            status__in=[
                PipelineItem.Status.INTERESTED,
                PipelineItem.Status.PREPARING,
                PipelineItem.Status.SUBMITTED,
            ],
            opportunity__deadline_date__gte=timezone.localdate(),
        )
        .select_related("opportunity")
        .order_by("opportunity__deadline_date", "pk")
    )
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//GrantRadar Africa//Funding Deadlines//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    stamp = timezone.now().strftime("%Y%m%dT%H%M%SZ")
    for item in items:
        opportunity = item.opportunity
        deadline = opportunity.deadline_date
        if deadline is None:
            continue
        description = f"{item.get_status_display()}: {opportunity.official_source_url}"
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:pipeline-{item.pk}@grantradar-africa",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{deadline:%Y%m%d}",
                f"DTEND;VALUE=DATE:{deadline + timedelta(days=1):%Y%m%d}",
                f"SUMMARY:{_escape_ical(opportunity.title)}",
                f"DESCRIPTION:{_escape_ical(description)}",
                f"URL:{_escape_ical(request.build_absolute_uri(opportunity.get_absolute_url()))}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    content = "\r\n".join(_fold_ical_line(line) for line in lines) + "\r\n"
    response = HttpResponse(content, content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="grantradar-deadlines.ics"'
    return response


def _escape_ical(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold_ical_line(line: str) -> str:
    segments: list[str] = []
    current = ""
    byte_count = 0
    for character in line:
        character_size = len(character.encode("utf-8"))
        if byte_count + character_size > 75:
            segments.append(current)
            current = f" {character}"
            byte_count = 1 + character_size
        else:
            current += character
            byte_count += character_size
    segments.append(current)
    return "\r\n".join(segments)
