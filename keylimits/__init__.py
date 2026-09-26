"""keylimits - check the rate limits and validity of API keys."""

from .checker import check_env, check_key, check_many
from .models import Allowance, Bucket, KeyLimits

__all__ = ["check_key", "check_many", "check_env", "KeyLimits", "Bucket", "Allowance", "__version__"]
__version__ = "0.1.0"