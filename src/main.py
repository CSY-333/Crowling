import argparse
import sys
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Add src to path to allow imports if running directly
sys.path.append(str(Path(__file__).parent.parent))

from src.config import load_config, get_default_config_path
from src.storage.db import Database
from src.ops.logger import setup_logger


@dataclass
class RuntimeContext:
    config: "AppConfig"
    db: Database
    run_id: str
    snapshot_at: str
    db_path: str


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

    # 0. Temporary logger for config loading
    logging.basicConfig(level=logging.INFO)
    temp_logger = logging.getLogger("bootstrap")

    try:
        config = load_config(args.config)
        temp_logger.info(f"Configuration loaded from {args.config}")
    except Exception as exc:
        temp_logger.error(f"Failed to load configuration: {exc}")
        raise

    # 1. Init Run ID & Logger
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logger(run_id)
    logger.info(f"Starting Run ID: {run_id}")

    if config.privacy.allow_pii:
        logger.warning("!!! WARNING: PII Collection is ENABLED (allow_pii=True) !!!")
        logger.warning("Ensure you have explicit consent or justification.")

    db_path = args.resume_from_db if args.resume_from_db else config.storage.db_path
    logger.info(f"Initializing database at {db_path}")

    db = Database(db_path, wal_mode=config.storage.wal_mode)
    try:
        db.init_schema()
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")
        raise

    snapshot_at = datetime.now().isoformat()

    return RuntimeContext(
        config=config,
        db=db,
        run_id=run_id,
        snapshot_at=snapshot_at,
        db_path=db_path,
    )


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

    # Initialize components
    from src.ops.evidence import EvidenceCollector
    from src.collectors.search_collector import SearchCollector
    from src.collectors.article_parser import ArticleParser
    from src.ops.probe import EndpointProbe
    from src.collectors.comment_collector import CommentCollector
    from src.collectors.comment_fetcher import CommentFetcher
    from src.collectors.comment_parser import CommentParser
    from src.storage.repository import CommentRepository
    from src.http.client import RequestsHttpClient
    from src.ops.rate_limiter import RateLimiter
    from src.ops.throttle import AutoThrottler
    from src.privacy.hashing import PrivacyHasher
    from src.storage.exporters import DataExporter

    http_client = RequestsHttpClient()
    evidence = EvidenceCollector(run_id=run_id, logs_dir="logs")
    searcher = SearchCollector(config.search, http_client)
    parser = ArticleParser(http_client)
    probe = EndpointProbe()
    
    # Privacy Setup
    salt = config.privacy.global_salt if config.privacy.hash_salt_mode == "global" else run_id
    if not salt:
        salt = run_id # Fallback
    hasher = PrivacyHasher(salt)

    rate_limiter = RateLimiter(config.collection.rate_limit)
    throttler = AutoThrottler(config.collection.auto_throttle, rate_limiter, db, run_id)
    fetcher = CommentFetcher(http_client, rate_limiter, throttler, evidence, config)
    comment_parser = CommentParser(config, hasher)
    repository = CommentRepository(db, run_id)
    
    collector = CommentCollector(config, fetcher, comment_parser, repository, snapshot_at)

    # 5. Pre-flight health check (Optional integration here, typically before loop)
    # from src.ops.health_check import HealthCheck
    # hc = HealthCheck(config)
    # if not hc.run_preflight_check():
    #     logger.critical("Pre-flight check failed. Aborting.")
    #     sys.exit(1)

    # 6. Main Collection Loop
    total_articles = 0
    total_comments = 0
    
    for keyword in config.search.keywords:
        logger.info(f"== Processing Keyword: {keyword} ==")
        
        for item in searcher.search_keyword(keyword):
            total_articles += 1
            url = item.get("url")
            oid = item.get("oid")
            aid = item.get("aid")
            title = item.get("title")
            
            if not oid or not aid:
                logger.warning(f"Skipping article without OID/AID: {url}")
                continue
                
            # Resume Check (via DB directly or collector helper)
            if repository.is_article_completed(oid, aid):
                logger.info(f"Skipping completed article: {oid}/{aid}")
                continue

            logger.info(f"Processing ({total_articles}) {oid}/{aid}: {title}")
            
            # 1. Parse Metadata
            meta = parser.fetch_and_parse(url)
            if meta["status_code"] != "CRAWL-OK":
                logger.error(f"Metadata parse failed for {url}: {meta.get('error_code')}")
                # Log usage if needed, but we continue to try comments? 
                # Usually if article is missing, comments might still exist? 
                # But we need OID/AID which we have.
                # PRD says we should try if OID/AID exists.
            
            # 2. Probe Endpoint
            raw_html = meta.get("_raw_html", "")
            candidates = probe.get_candidate_configs(url, raw_html)
            
            # 3. Collect Comments (Try candidates)
            success = False
            for params in candidates:
                try:
                    count = collector.collect_article(oid, aid, params)
                    total_comments += count
                    success = True
                    break # Success!
                except Exception as e:
                    logger.warning(f"Probe config failed for {oid}/{aid}: {e}")
                    # Continue to next candidate
            
            if not success:
                logger.error(f"All probe candidates failed for {oid}/{aid}")
                # Article status is updated inside collect_article (on fail)
                
            # Volume Check (Optional: check total comments vs target)
            if config.volume_strategy.target_comments and total_comments >= config.volume_strategy.target_comments:
                logger.info(f"Target volume reached ({total_comments}). Stopping.")
                sys.exit(0)

    logger.info(f"Run Complete. Articles: {total_articles}, Comments: {total_comments}")
    
    # 7. Export Data
    exporter = DataExporter(db)
    exporter.export_run(run_id)

if __name__ == "__main__":
    main()
