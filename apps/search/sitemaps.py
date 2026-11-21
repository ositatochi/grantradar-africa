from datetime import datetime

from django.contrib.sitemaps import Sitemap
from django.db.models import Count, Q
from django.urls import reverse

from apps.funders.models import Funder
from apps.opportunities.models import Opportunity
from apps.search.services import public_opportunities


class OpportunitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.8

    def items(self) -> list[Opportunity]:
        return list(public_opportunities().order_by("pk"))

    def lastmod(self, item: Opportunity) -> datetime:
        return item.date_last_verified or item.updated_at


class FunderSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self) -> list[Funder]:
        funders = Funder.objects.filter(is_active=True).annotate(
            public_count=Count(
                "opportunities",
                filter=Q(opportunities__date_last_verified__isnull=False)
                & ~Q(opportunities__status=Opportunity.Status.UNVERIFIED)
                & ~Q(opportunities__official_source_url=""),
                distinct=True,
            )
        )
        return list(funders.filter(public_count__gt=0))

    def location(self, item: Funder) -> str:
        return reverse("search:funder-detail", kwargs={"slug": item.slug})
