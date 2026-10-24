"""Allow ``python -m schemaflow``."""

import sys

from .cli import main

sys.exit(main())
