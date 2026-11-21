# Initial data model (planned)

This Phase 0 diagram records the intended domain relationships. It is not a schema contract: fields, constraints, and deletion policies will be specified and tested when the models are implemented in Phase 1.

```mermaid
erDiagram
    FUNDER ||--o{ OPPORTUNITY : offers
    OPPORTUNITY ||--o{ OPPORTUNITY_SOURCE : attributed_to
    SOURCE ||--o{ OPPORTUNITY_SOURCE : reports
    SOURCE ||--o{ SOURCE_RUN : executes
    SOURCE_RUN ||--o{ RAW_DOCUMENT : captures
    SECTOR }o--o{ OPPORTUNITY : classifies
    COUNTRY }o--o{ OPPORTUNITY : eligibility
    APPLICANT_TYPE }o--o{ OPPORTUNITY : permits
    USER ||--o{ SAVED_SEARCH : owns
    SAVED_SEARCH ||--o{ ALERT : schedules
    ALERT ||--o{ ALERT_DELIVERY : sends
    USER ||--o{ BOOKMARK : saves
    OPPORTUNITY ||--o{ BOOKMARK : bookmarked
    USER ||--o{ PIPELINE_ITEM : tracks
    OPPORTUNITY ||--o{ PIPELINE_ITEM : tracked
    PIPELINE_ITEM ||--o{ NOTE : includes
    TEAM ||--o{ TEAM_MEMBER : includes
    USER ||--o{ TEAM_MEMBER : joins
    TEAM ||--o{ COMMENT : receives
    USER ||--o{ COMMENT : writes
    CANDIDATE_SOURCE }o--o| SOURCE : promoted_to
    OPPORTUNITY ||--o{ ERROR_REPORT : reported
    USER ||--o{ ERROR_REPORT : submits
    USER ||--o{ API_TOKEN : owns
    USER ||--o{ AUDIT_LOG : acts
```

`User` refers to Django's configured user model. Many-to-many relationships shown above will use explicit through models where metadata or auditability is required.
