import logging
import os

logger = logging.getLogger("spoofspy.deployment")


def is_prod_deployment() -> bool:
    debug = os.environ.get("SPOOFSPY_DEBUG")
    logger.info("SPOOFSPY_DEBUG=%s", debug)
    is_dbg = debug and (str(debug).lower() in ("true", "on", "1"))
    return not is_dbg
