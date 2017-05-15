import sys
import logging

# Useful to debug threading issues.
logging.basicConfig(
    stream=sys.stderr,
    # Change level to DEBUG here if you need to.
    level=logging.CRITICAL,
    format='%(process)d %(thread)d: %(message)s'
)
