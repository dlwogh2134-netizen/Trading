from typing import Final


NEWS_ARTICLE_SELECT: Final[str] = (
    "id,market,source,source_article_id,title,summary,url,published_at,fetched_at,"
    "company_name,symbol,language,sentiment,content_hash,is_active,raw_payload,"
    "ai_summary,ai_summary_model,ai_summary_generated_at,ai_summary_prompt_version,"
    "quality_status,relevance_score,excluded_reason,quality_checked_at"
)
HIGH_QUALITY_STATUS: Final[str] = "HIGH_QUALITY"
DEFAULT_QUALITY_STATUS: Final[str] = "PASS"
DEFAULT_RELEVANCE_SCORE: Final[int] = 45
GENERAL_NEWS_VISIBLE_DAYS: Final[int] = 7
HIGH_QUALITY_NEWS_VISIBLE_DAYS: Final[int] = 30
VISIBLE_QUALITY_STATUS_FILTER: Final[str] = "in.(PASS,HIGH_QUALITY,LOW_CONFIDENCE)"
SYMBOL_ARTICLE_ORDER: Final[str] = (
    "published_at.desc,relevance_score.desc.nullslast,quality_status.asc.nullslast"
)
