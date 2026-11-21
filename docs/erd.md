# Phase 1 data model

This diagram reflects the implemented Phase 1 model relationships. Search, alert delivery, pipeline, and team workflows are represented in the schema but are not yet user-facing features.

```mermaid
erDiagram
    USER ||--o{ AUDIT_LOG : performs
    USER ||--o{ SAVED_SEARCH : owns
    USER ||--o{ BOOKMARK : saves
    USER ||--o{ PIPELINE_ITEM : tracks
    USER ||--o{ TEAM : owns
    USER ||--o{ TEAM_MEMBER : joins
    USER ||--o{ COMMENT : writes
    USER ||--o{ API_TOKEN : owns
    USER ||--o{ ERROR_REPORT : submits
    FUNDER ||--o{ OPPORTUNITY : offers
    OPPORTUNITY ||--o{ OPPORTUNITY_SOURCE : attributed_to
    SOURCE ||--o{ OPPORTUNITY_SOURCE : reports
    SOURCE ||--o{ SOURCE_RUN : executes
    SOURCE_RUN ||--o{ RAW_DOCUMENT : captures
    SOURCE ||--o{ RAW_DOCUMENT : archives
    SOURCE ||--o{ CANDIDATE_SOURCE : promoted_from
    SEARCH_QUERY ||--o{ CANDIDATE_SOURCE : discovers
    SECTOR }o--o{ OPPORTUNITY : classifies
    SECTOR }o--o{ SOURCE : tagged
    COUNTRY }o--o{ OPPORTUNITY : eligible
    COUNTRY }o--o{ OPPORTUNITY : excluded
    COUNTRY }o--o{ SOURCE : tagged
    APPLICANT_TYPE }o--o{ OPPORTUNITY : permits
    THEME }o--o{ OPPORTUNITY : tags
    CURRENCY ||--o{ OPPORTUNITY : amounts
    SDG ||--o{ SECTOR : aligns
    SAVED_SEARCH ||--o{ ALERT : schedules
    ALERT ||--o{ ALERT_DELIVERY : sends
    OPPORTUNITY ||--o{ BOOKMARK : bookmarked
    OPPORTUNITY ||--o{ PIPELINE_ITEM : tracked
    TEAM ||--o{ PIPELINE_ITEM : shares
    PIPELINE_ITEM ||--o{ NOTE : includes
    TEAM ||--o{ TEAM_MEMBER : includes
    TEAM ||--o{ COMMENT : receives
    OPPORTUNITY ||--o{ COMMENT : receives
    OPPORTUNITY ||--o{ ERROR_REPORT : reported
```

`OpportunitySource` is the explicit through model for opportunity/source attribution. The configured user model is `accounts.User`. Countries, currencies, and taxonomies are populated with `seed_reference_data`; monitored sources are loaded from `sources.yaml`.
