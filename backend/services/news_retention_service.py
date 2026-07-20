from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

import requests


@dataclass(frozen=True, slots=True)
class NewsRetentionCleanupCounts:
    normal_news: int
    high_quality_news: int
    logs: int


@dataclass(frozen=True, slots=True)
class DisclosureRetentionCleanupCounts:
    disclosures: int = 0
    analyses: int = 0
    chunks: int = 0
    batches: int = 0


class DisclosureRetentionDeleteError(RuntimeError):
    def __init__(self, *, status_code: int, response_text: str) -> None:
        self.table = "rpc/cleanup_expired_disclosures"
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(
            f"Supabase 공시 보존 기간 정리 실패: status_code={status_code}"
        )


class NewsRetentionDeleteError(RuntimeError):
    def __init__(self, *, table: str, status_code: int, response_text: str) -> None:
        self.table = table
        self.status_code = status_code
        self.response_text = response_text
        super().__init__(
            f"Supabase 뉴스 보관 삭제 실패: table={table}, status_code={status_code}"
        )


class _DeleteResponse(Protocol):
    status_code: int
    text: str
    headers: Mapping[str, str]


class NewsRetentionCleaner:
    def __init__(self, *, supabase_url: str, service_role_key: str) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key

    @property
    def is_configured(self) -> bool:
        return bool(self.supabase_url and self.service_role_key)

    def cleanup_expired(self, now: datetime | None = None) -> NewsRetentionCleanupCounts:
        if not self.is_configured:
            return NewsRetentionCleanupCounts(normal_news=0, high_quality_news=0, logs=0)

        retention_now = now or datetime.now(timezone.utc)
        if retention_now.tzinfo is None:
            retention_now = retention_now.replace(tzinfo=timezone.utc)
        retention_now = retention_now.astimezone(timezone.utc).replace(microsecond=0)

        high_quality_count = self._delete_with_count(
            "news_articles",
            {
                "quality_status": "eq.HIGH_QUALITY",
                "published_at": f"lt.{(retention_now - timedelta(days=30)).isoformat()}",
            },
        )
        normal_count = self._delete_with_count(
            "news_articles",
            {
                "or": "(quality_status.neq.HIGH_QUALITY,quality_status.is.null)",
                "published_at": f"lt.{(retention_now - timedelta(days=7)).isoformat()}",
            },
        )
        log_count = self._delete_with_count(
            "news_fetch_logs",
            {"started_at": f"lt.{(retention_now - timedelta(days=7)).isoformat()}"},
        )
        return NewsRetentionCleanupCounts(
            normal_news=normal_count,
            high_quality_news=high_quality_count,
            logs=log_count,
        )

    def _delete_headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "count=exact,return=minimal",
        }

    def _delete_with_count(self, table: str, params: dict[str, str]) -> int:
        response = requests.delete(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._delete_headers(),
            params=params,
            timeout=30,
        )
        if response.status_code not in (200, 204):
            raise NewsRetentionDeleteError(
                table=table,
                status_code=response.status_code,
                response_text=response.text,
            )
        return self._parse_deleted_count(response)

    def _parse_deleted_count(self, response: _DeleteResponse) -> int:
        content_range = response.headers.get("Content-Range", "")
        total = content_range.rsplit("/", 1)[-1].strip()
        if not total or total == "*":
            return 0
        return int(total)


class DisclosureRetentionCleaner:
    BATCH_SIZE = 5000

    def __init__(self, *, supabase_url: str, service_role_key: str) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key

    @property
    def is_configured(self) -> bool:
        return bool(self.supabase_url and self.service_role_key)

    def cleanup_expired(
        self,
        now: datetime | None = None,
    ) -> DisclosureRetentionCleanupCounts:
        if not self.is_configured:
            return DisclosureRetentionCleanupCounts()

        retention_now = now or datetime.now(timezone.utc)
        if retention_now.tzinfo is None:
            retention_now = retention_now.replace(tzinfo=timezone.utc)
        korea_date = retention_now.astimezone(timezone(timedelta(hours=9))).date()
        cutoff_date = korea_date - timedelta(days=30)
        totals = DisclosureRetentionCleanupCounts()

        while True:
            batch = self._delete_batch(cutoff_date.isoformat())
            totals = DisclosureRetentionCleanupCounts(
                disclosures=totals.disclosures + batch["deleted_disclosures"],
                analyses=totals.analyses + batch["deleted_analyses"],
                chunks=totals.chunks + batch["deleted_chunks"],
                batches=totals.batches + 1,
            )
            if not batch["has_more"]:
                return totals

    def _delete_batch(self, cutoff_date: str) -> dict[str, int | bool]:
        response = requests.post(
            f"{self.supabase_url}/rest/v1/rpc/cleanup_expired_disclosures",
            headers={
                "apikey": self.service_role_key,
                "Authorization": f"Bearer {self.service_role_key}",
                "Content-Type": "application/json",
            },
            json={
                "p_cutoff_date": cutoff_date,
                "p_batch_size": self.BATCH_SIZE,
            },
            timeout=60,
        )
        if response.status_code not in (200, 201):
            raise DisclosureRetentionDeleteError(
                status_code=response.status_code,
                response_text=response.text,
            )

        payload = response.json()
        row = payload[0] if isinstance(payload, list) and payload else payload
        if not isinstance(row, dict):
            raise DisclosureRetentionDeleteError(
                status_code=200,
                response_text=response.text,
            )
        return {
            "deleted_disclosures": int(row.get("deleted_disclosures") or 0),
            "deleted_analyses": int(row.get("deleted_analyses") or 0),
            "deleted_chunks": int(row.get("deleted_chunks") or 0),
            "has_more": bool(row.get("has_more")),
        }
