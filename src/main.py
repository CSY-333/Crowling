import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add src to path to allow imports if running directly
sys.path.append(str(Path(__file__).parent.parent))

from src.common.errors import AppError, Severity
from src.config import load_config, get_default_config_path
from src.ops.logger import setup_logger
from src.ops.run_events import RunEventLogger
from src.ops.run_metrics import compute_tier_outcome, compute_health_score
from src.ops.structural import StructuralError
from src.ops.volume import VolumeTracker
from src.privacy.factory import build_privacy_hasher
from src.storage.db import Database


@dataclass
class RuntimeContext:
    config: "AppConfig"
    db: Database
    run_id: str
    snapshot_at: str
    db_path: str


@dataclass
class RunLoopStats:
    total_articles: int = 0
    total_comments: int = 0


@dataclass
class RunLoopResult:
    stop_reason: Optional[str] = None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="NACT-MVP: Naver Article & Comment Tracker")

    parser.add_argument(
        "--config",
        type=str,
        default=str(get_default_config_path()),
        help="Path to the YAML configuration file.",
    )

    parser.add_argument(
        "--resume-from-db",
        type=str,
        help="Path to an existing SQLite DB to resume from.",
    )

    return parser.parse_args(argv)


def bootstrap_runtime(args) -> RuntimeContext:
    logging.basicConfig(level=logging.INFO)
    temp_logger = logging.getLogger("bootstrap")

    try:
        config = load_config(args.config)
        temp_logger.info("Configuration loaded from %s", args.config)
    except Exception as exc:
        temp_logger.error("Failed to load configuration: %s", exc)
        raise

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logger(run_id)
    logger.info("Starting Run ID: %s", run_id)

    if config.privacy.allow_pii:
        logger.warning("!!! WARNING: PII Collection is ENABLED (allow_pii=True) !!!")
        logger.warning("Ensure you have explicit consent or justification.")

    db_path = args.resume_from_db if args.resume_from_db else config.storage.db_path
    logger.info("Initializing database at %s", db_path)

    db = Database(db_path, wal_mode=config.storage.wal_mode)
    db.init_schema()

    snapshot_at = datetime.now().isoformat()

    return RuntimeContext(
        config=config,
        db=db,
        run_id=run_id,
        snapshot_at=snapshot_at,
        db_path=db_path,
    )


def run_collection_loop(
    config,
    searcher,
    parser,
    probe,
    collector,
    repository,
    stop_strategy,
    volume_tracker: VolumeTracker,
    event_logger: RunEventLogger,
    stats: RunLoopStats,
) -> RunLoopResult:
    logger = logging.getLogger("nact-mvp")
    stop_reason: Optional[str] = None
    stop_triggered = False

    for keyword in config.search.keywords:
        if stop_triggered:
            break
        logger.info("== Processing Keyword: %s ==", keyword)

        for item in searcher.search_keyword(keyword):
            url = item.get("url")
            oid = item.get("oid")
            aid = item.get("aid")
            title = item.get("title")

            if not oid or not aid:
                logger.warning("Skipping article without OID/AID: %s", url)
                continue

            stats.total_articles += 1
            logger.info("Processing (%d) %s/%s: %s", stats.total_articles, oid, aid, title)

            if repository.is_article_completed(oid, aid):
                logger.info("Skipping completed article: %s/%s", oid, aid)
                continue

            metadata = parser.fetch_and_parse(url)
            if metadata.get("status") != "CRAWL-OK":
                logger.warning(
                    "Metadata parse flagged %s/%s: %s",
                    oid,
                    aid,
                    metadata.get("error_code") or metadata.get("error_message"),
                )

            raw_html = metadata.get("_raw_html", "")
            candidates = list(probe.get_candidate_configs(url, raw_html))

            if not candidates:
                repository.set_article_status(
                    oid,
                    aid,
                    status="FAIL-NOCAND",
                    error_code="NO_CANDIDATE",
                    error_message="Probe did not emit any comment API candidates.",
                )
                event_logger.log(
                    "CANDIDATE_MISSING",
                    "Probe produced zero candidates",
                    {"oid": oid, "aid": aid, "url": url or ""},
                )
                continue

            success = False
            for attempt, params in enumerate(candidates, start=1):
                ctx_payload = {
                    "oid": oid,
                    "aid": aid,
                    "attempt": str(attempt),
                    "params": json.dumps(params, ensure_ascii=False),
                }

                try:
                    count = collector.collect_article(oid, aid, params, source_url=url)
                    stats.total_comments += count
                    volume_tracker.add_count(count)
                    success = True
                    break
                except StructuralError:
                    raise
                except AppError as exc:
                    event_type = "CANDIDATE_RETRY" if exc.severity == Severity.RETRY else "CANDIDATE_FAIL"
                    event_logger.log(event_type, str(exc), ctx_payload)
                    if exc.severity == Severity.RETRY:
                        continue
                    break
                except Exception as exc:
                    event_logger.log("CANDIDATE_EXCEPTION", str(exc), ctx_payload)
                    raise

            if not success:
                logger.error("All probe candidates failed for %s/%s", oid, aid)

            if stop_strategy and not stop_triggered:
                decision = stop_strategy.decide(stats.total_comments, 0.0)
                if decision.should_stop:
                    stop_reason = decision.reason or "TARGET_REACHED"
                    logger.info(
                        "Volume strategy triggered stop (%s) at %d comments",
                        stop_reason,
                        stats.total_comments,
                    )
                    stop_triggered = True
                    break

            remaining_capacity = max(0, config.volume_strategy.max_total_articles - stats.total_articles)
            if volume_tracker.should_expand(
                target_comments=config.volume_strategy.target_comments,
                collected_comments=stats.total_comments,
                remaining_capacity=remaining_capacity,
            ):
                logger.warning("Volume tracker suggests expanding search scope to meet targets.")

    return RunLoopResult(stop_reason=stop_reason)


def main():
    args = parse_args()

    try:
        context = bootstrap_runtime(args)
    except Exception:
        sys.exit(1)

    config = context.config
    db = context.db
    run_id = context.run_id
    snapshot_at = context.snapshot_at

    logger = logging.getLogger("nact-mvp")

    from src.collectors.article_parser import ArticleParser
    from src.collectors.comment_collector import CommentCollector
    from src.collectors.comment_fetcher import CommentFetcher
    from src.collectors.comment_parser import CommentParser
    from src.collectors.comment_stats import CommentStatsService
    from src.collectors.search_collector import SearchCollector
    from src.http.client import RequestsHttpClient
    from src.ops.evidence import EvidenceCollector
    from src.ops.probe import EndpointProbe
    from src.ops.rate_limiter import RateLimiter
    from src.ops.throttle import AutoThrottler
    from src.ops.volume_strategy import FixedTargetStrategy
    from src.storage.exporters import DataExporter
    from src.storage.repository import CommentRepository
    from src.storage.run_repository import RunRepository

    http_client = RequestsHttpClient()
    evidence = EvidenceCollector(run_id=run_id, logs_dir="logs")
    searcher = SearchCollector(config.search, http_client)
    parser = ArticleParser(http_client)
    probe = EndpointProbe()

    hasher, _ = build_privacy_hasher(config.privacy, run_id)
    comment_parser = CommentParser(config, hasher)

    event_logger = RunEventLogger(db, run_id)

    rate_limiter = RateLimiter(config.collection.rate_limit)
    throttler = AutoThrottler(config.collection.auto_throttle, rate_limiter, db, run_id, event_logger=event_logger)
    fetcher = CommentFetcher(http_client, rate_limiter, throttler, evidence, config)

    repository = CommentRepository(db, run_id, store_author_raw=config.privacy.allow_pii)
    stats_service = CommentStatsService(
        http_client=http_client,
        evidence=evidence,
        config=config.collection.comment_stats,
        parse_jsonp=comment_parser.parse_jsonp,
    )
    collector = CommentCollector(
        config,
        fetcher,
        comment_parser,
        repository,
        snapshot_at,
        event_logger=event_logger,
        stats_service=stats_service,
    )
    volume_tracker = VolumeTracker()
    run_repo = RunRepository(db)
    run_repo.start_run(
        run_id=run_id,
        snapshot_at=snapshot_at,
        tz_name=config.snapshot.timezone,
        config_payload=config.model_dump(),
    )

    stop_strategy = None
    if config.volume_strategy.target_comments:
        stop_strategy = FixedTargetStrategy(config.volume_strategy.target_comments)

    exporter = DataExporter(db)
    loop_stats = RunLoopStats()
    stop_reason: Optional[str] = None
    failure_reason: Optional[str] = None
    run_status = "FAILED"

    try:
        result = run_collection_loop(
            config,
            searcher,
            parser,
            probe,
            collector,
            repository,
            stop_strategy,
            volume_tracker,
            event_logger,
            loop_stats,
        )
        stop_reason = result.stop_reason
        run_status = "STOPPED" if stop_reason else "SUCCESS"
        logger.info(
            "Run Complete. Articles: %d, Comments: %d",
            loop_stats.total_articles,
            loop_stats.total_comments,
        )
    except StructuralError as exc:
        failure_reason = str(exc)
        run_status = "FAILED"
        logger.critical("Structural failure aborted run: %s", exc)
    except Exception as exc:
        failure_reason = str(exc)
        run_status = "PARTIAL"
        logger.exception("Run terminated unexpectedly.")
    finally:
        try:
            exporter.export_run(run_id)
        except Exception as exc:
            logger.exception("Export failed: %s", exc)

        volume_grade, tier_note = compute_tier_outcome(
            total_comments=loop_stats.total_comments,
            target_comments=config.volume_strategy.target_comments,
            minimum_comments=config.volume_strategy.min_acceptable_comments,
        )
        health_score, needs_review = compute_health_score(
            duplicate_rate=0.0,
            timestamp_anomalies=0,
            total_mismatch=volume_grade == "C",
        )
        notes_parts = [f"volume_grade={volume_grade}:{tier_note}"]
        if stop_reason:
            notes_parts.append(f"stop_reason={stop_reason}")
        if failure_reason:
            notes_parts.append(f"failure={failure_reason}")
        notes = " | ".join(notes_parts)

        run_repo.finalize_run(
            run_id=run_id,
            status=run_status,
            notes=notes,
            total_articles=loop_stats.total_articles,
            total_comments=loop_stats.total_comments,
            health_score=health_score,
            health_flags="technical_review_needed" if needs_review else "",
        )

    if run_status == "FAILED":
        sys.exit(2)
    if run_status == "PARTIAL":
        sys.exit(3)


if __name__ == "__main__":
    main()
