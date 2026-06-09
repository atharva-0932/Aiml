-- V004: Create internal stage for bulk COPY INTO loads + set warehouse auto-suspend
-- AUTO_SUSPEND = 60 prevents burning free trial credits when idle

ALTER WAREHOUSE COMPUTE_WH SET AUTO_SUSPEND = 60 AUTO_RESUME = TRUE;

CREATE OR REPLACE STAGE aml_stage
    FILE_FORMAT = (
        TYPE = 'CSV'
        FIELD_OPTIONALLY_ENCLOSED_BY = '"'
        SKIP_HEADER = 1
        NULL_IF = ('NULL', 'null', '')
        EMPTY_FIELD_AS_NULL = TRUE
    )
    COMMENT = 'Internal stage for AML bulk data loads';
