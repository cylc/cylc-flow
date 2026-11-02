#!/usr/bin/env bash
# Custom tailer that honours the %(lines)s substitution so the test can prove
# that "cylc cat-log" passes the correct line count for each view mode:
#   * tail-from-start mode  -> cylc substitutes "+1"  -> whole file
#   * tail-end mode         -> cylc substitutes "N"   -> last N lines
# Prefix output with HELLO to prove cylc used this custom tailer.
# Exit immediately (i.e. don't follow) so the test does not block.
LINES="$1"
FILE="$2"
tail -n "${LINES}" "${FILE}" | awk '{print "HELLO", $0; fflush() }'
