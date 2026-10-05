"""Optional error monitoring. Does nothing unless config.SENTRY_DSN is set —
every other module can call capture_error() unconditionally and it's a safe
no-op until you configure a DSN. See config.py for how to enable it.
"""
import logging

import config

logger = logging.getLogger(__name__)

_sentry_enabled = False


def init_monitoring(service_name: str):
    """Call once at process startup (api_server.py and bot.py each call this
    for themselves — they're separate processes)."""
    global _sentry_enabled
    if not config.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=config.SENTRY_DSN,
            environment=service_name,
            traces_sample_rate=0.0,  # error tracking only, no perf tracing overhead
        )
        _sentry_enabled = True
        logger.info(f"[monitoring] Sentry initialized for {service_name}")
    except ImportError:
        logger.warning(
            "[monitoring] SENTRY_DSN is set but the sentry-sdk package isn't "
            "installed — run `pip install sentry-sdk` to enable error tracking."
        )
    except Exception:
        logger.exception("[monitoring] Sentry init failed — continuing without it")


def capture_error(message: str):
    """Report a handled-but-notable error. Safe to call whether or not
    monitoring is configured; it just logs if Sentry isn't set up."""
    if _sentry_enabled:
        try:
            import sentry_sdk
            sentry_sdk.capture_message(message, level="error")
            return
        except Exception:
            logger.exception("[monitoring] failed to report to Sentry")
    logger.error(f"[monitoring] {message}")
