"""P-Trojan poisoner for the local OpenBackdoor QA pipeline.

The poisoning format is identical to GBTL after a discrete trigger has been
learned.  The distinction is in how that trigger is optimized; see
``learn_ptrojan_trigger.py``.
"""

from typing import Optional

from openbackdoor.utils import logger

from .gbtl_poisoner import GBTLPoisoner


class PTrojanPoisoner(GBTLPoisoner):
    """Insert a persistence-aware trigger and construct poisoned QA targets.

    This class intentionally inherits the mature QA target handling in
    :class:`GBTLPoisoner` (string/list answers and append, prefix, keyword or
    rewrite payload modes).  It only changes validation/logging because the
    attack-specific optimization happens before poisoning.
    """

    def __init__(
        self,
        trigger: Optional[str] = None,
        trigger_path: Optional[str] = None,
        **kwargs,
    ):
        if trigger is None and trigger_path is None:
            raise ValueError(
                "P-Trojan requires either `trigger` or `trigger_path`. "
                "Run learn_ptrojan_trigger.py first."
            )

        super().__init__(
            trigger=trigger,
            trigger_path=trigger_path,
            **kwargs,
        )

        logger.info(
            "Initializing P-Trojan poisoner | trigger=%r | trigger_path=%r",
            self.trigger,
            self.trigger_path,
        )

