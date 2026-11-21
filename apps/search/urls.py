from django.contrib.sitemaps.views import sitemap
from django.urls import path

from apps.search import views
from apps.search.sitemaps import FunderSitemap, OpportunitySitemap

app_name = "search"
sitemaps = {
    "opportunities": OpportunitySitemap,
    "funders": FunderSitemap,
}

urlpatterns = [
    path("", views.home, name="home"),
    path("opportunities/", views.opportunity_list, name="opportunity-list"),
    path(
        "opportunities/<int:pk>/<slug:slug>/",
        views.opportunity_detail,
        name="opportunity-detail",
    ),
    path(
        "opportunities/<int:pk>/<slug:slug>/report/",
        views.report_error,
        name="report-error",
    ),
    path("funders/", views.funder_list, name="funder-list"),
    path("funders/<slug:slug>/", views.funder_detail, name="funder-detail"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("robots.txt", views.robots_txt, name="robots"),
]
