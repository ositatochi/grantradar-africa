from __future__ import annotations

from datetime import timedelta
from typing import Any

from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import slugify
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from django_ratelimit.decorators import ratelimit

from apps.core.models import Country
from apps.funders.models import Funder
from apps.opportunities.models import ErrorReport, Opportunity
from apps.search.forms import OpportunitySearchForm
from apps.search.services import (
    PAGE_SIZE,
    apply_search_filters,
    opportunity_queryset_for_display,
    order_opportunities,
    paginated_meilisearch_results,
    public_opportunities,
)


class ErrorReportForm(forms.ModelForm):
    class Meta:
        model = ErrorReport
        fields = ["description"]
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Tell us what needs correcting.",
                }
            )
        }


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    today = timezone.localdate()
    public = opportunity_queryset_for_display(public_opportunities())
    closing = public.filter(
        status__in=[Opportunity.Status.OPEN, Opportunity.Status.CLOSING_SOON],
        deadline_date__gte=today,
    ).order_by("deadline_date", "title")
    nigeria = Country.objects.filter(alpha_2="NG").first()
    africa = Country.objects.filter(region="Africa")
    nigeria_opportunities = (
        public.filter(Q(eligible_countries=nigeria) | Q(eligible_countries__isnull=True)).distinct()
        if nigeria
        else public.filter(eligible_countries__isnull=True)
    )
    africa_opportunities = public.filter(
        Q(eligible_countries__in=africa) | Q(eligible_countries__isnull=True)
    ).distinct()
    context = {
        "new_today": public.filter(date_first_found__date=today).order_by("-date_first_found")[:6],
        "closing_by_window": [
            {
                "days": days,
                "end": today + timedelta(days=days),
                "opportunities": closing.filter(deadline_date__lte=today + timedelta(days=days))[
                    :6
                ],
            }
            for days in (7, 14, 30)
        ],
        "nigeria_opportunities": nigeria_opportunities.order_by("deadline_date")[:6],
        "africa_opportunities": africa_opportunities.order_by("deadline_date")[:6],
        "rolling_opportunities": public.filter(
            Q(rolling=True) | Q(status=Opportunity.Status.ROLLING)
        ).order_by("-date_last_verified")[:6],
        "today": today,
        "nigeria_id": nigeria.pk if nigeria else "",
        "canonical_url": request.build_absolute_uri("/"),
    }
    return render(request, "search/home.html", context)


@require_GET
def opportunity_list(request: HttpRequest) -> HttpResponse:
    form = OpportunitySearchForm(request.GET)
    warning = ""
    page_obj = None
    if form.is_valid():
        filters: dict[str, Any] = form.cleaned_data
        queryset = apply_search_filters(public_opportunities(), filters)
        query = filters.get("q", "")
        sort = filters.get("sort") or "relevance"
        if query:
            page_obj, warning = paginated_meilisearch_results(
                opportunity_queryset_for_display(queryset),
                query,
                filters,
                request.GET.get("page"),
            )
        if page_obj is None:
            if query:
                queryset = apply_search_filters(public_opportunities(), filters)
            queryset = order_opportunities(queryset, sort)
            page_obj = Paginator(opportunity_queryset_for_display(queryset), PAGE_SIZE).get_page(
                request.GET.get("page")
            )
    else:
        page_obj = Paginator([], PAGE_SIZE).get_page(1)

    context = {
        "form": form,
        "page_obj": page_obj,
        "warning": warning,
        "canonical_url": request.build_absolute_uri(reverse("search:opportunity-list")),
        "robots": "noindex,follow",
        "previous_page_url": _page_url(request, page_obj.previous_page_number())
        if page_obj.has_previous()
        else "",
        "next_page_url": _page_url(request, page_obj.next_page_number())
        if page_obj.has_next()
        else "",
    }
    return render(request, "search/opportunity_list.html", context)


@require_GET
def opportunity_detail(request: HttpRequest, pk: int, slug: str) -> HttpResponse:
    opportunity = get_object_or_404(
        opportunity_queryset_for_display(public_opportunities()),
        pk=pk,
    )
    canonical_path = opportunity.get_absolute_url()
    if slug != slugify(opportunity.title):
        return redirect(canonical_path, permanent=True)

    similar = (
        public_opportunities()
        .filter(sectors__in=opportunity.sectors.all())
        .exclude(pk=opportunity.pk)
        .distinct()
        .select_related("funder", "currency")
        .prefetch_related("sectors", "source_links__source")
        .order_by("deadline_date")[:4]
    )
    return render(
        request,
        "search/opportunity_detail.html",
        {
            "opportunity": opportunity,
            "similar_opportunities": similar,
            "error_form": ErrorReportForm(),
            "canonical_url": request.build_absolute_uri(canonical_path),
        },
    )


@ratelimit(key="ip", rate="5/h", method="POST", block=True)
def report_error(request: HttpRequest, pk: int, slug: str) -> HttpResponse:
    opportunity = get_object_or_404(public_opportunities(), pk=pk)
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    form = ErrorReportForm(request.POST)
    if form.is_valid():
        report: ErrorReport = form.save(commit=False)
        report.opportunity = opportunity
        report.source_url = opportunity.official_source_url
        report.submitted_by = request.user if request.user.is_authenticated else None
        report.save()
        messages.success(request, "Thank you. Your report has been sent for review.")
        return redirect(opportunity.get_absolute_url())
    return render(
        request,
        "search/opportunity_detail.html",
        {
            "opportunity": opportunity,
            "similar_opportunities": [],
            "error_form": form,
            "canonical_url": request.build_absolute_uri(opportunity.get_absolute_url()),
        },
        status=400,
    )


@require_GET
def funder_list(request: HttpRequest) -> HttpResponse:
    funders = Funder.objects.filter(is_active=True).annotate(
        opportunity_count=Count(
            "opportunities",
            filter=Q(opportunities__date_last_verified__isnull=False)
            & ~Q(opportunities__status=Opportunity.Status.UNVERIFIED)
            & ~Q(opportunities__official_source_url=""),
            distinct=True,
        )
    )
    funders = funders.filter(opportunity_count__gt=0).order_by("name")
    page_obj = Paginator(funders, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "search/funder_list.html",
        {
            "page_obj": page_obj,
            "canonical_url": request.build_absolute_uri(reverse("search:funder-list")),
            "previous_page_url": _page_url(request, page_obj.previous_page_number())
            if page_obj.has_previous()
            else "",
            "next_page_url": _page_url(request, page_obj.next_page_number())
            if page_obj.has_next()
            else "",
        },
    )


@require_GET
def funder_detail(request: HttpRequest, slug: str) -> HttpResponse:
    funder = get_object_or_404(
        Funder.objects.filter(is_active=True).annotate(
            public_count=Count(
                "opportunities",
                filter=Q(opportunities__date_last_verified__isnull=False)
                & ~Q(opportunities__status=Opportunity.Status.UNVERIFIED)
                & ~Q(opportunities__official_source_url=""),
                distinct=True,
            )
        ),
        slug=slug,
        public_count__gt=0,
    )
    opportunities = opportunity_queryset_for_display(
        public_opportunities().filter(funder=funder).order_by("deadline_date", "title")
    )
    page_obj = Paginator(opportunities, PAGE_SIZE).get_page(request.GET.get("page"))
    return render(
        request,
        "search/funder_detail.html",
        {
            "funder": funder,
            "page_obj": page_obj,
            "canonical_url": request.build_absolute_uri(
                reverse("search:funder-detail", kwargs={"slug": funder.slug})
            ),
            "previous_page_url": _page_url(request, page_obj.previous_page_number())
            if page_obj.has_previous()
            else "",
            "next_page_url": _page_url(request, page_obj.next_page_number())
            if page_obj.has_next()
            else "",
        },
    )


@require_GET
def robots_txt(request: HttpRequest) -> HttpResponse:
    sitemap_url = request.build_absolute_uri(reverse("search:sitemap"))
    return HttpResponse(
        f"User-agent: *\nAllow: /\nSitemap: {sitemap_url}\n",
        content_type="text/plain",
    )


def _page_url(request: HttpRequest, page_number: int) -> str:
    query = request.GET.copy()
    query["page"] = str(page_number)
    return f"{request.path}?{query.urlencode()}"
