#!/bin/bash

# Change "script = false" -> "true" in 1/foo, then reload and retrigger it.

if grep "\[command\] reload_workflow" "${CYLC_WORKFLOW_LOG_DIR}/log" >/dev/null; then
    # Abort if not the first call (avoid an endless loop if the reload does not
    # have the intended effect).
    >&2 echo "ERROR (stall-handler.sh): should only be called once"
    cylc stop --now --now "${CYLC_WORKFLOW_ID}"
    exit 1
fi
sed -i "s/false/true/" "${CYLC_WORKFLOW_RUN_DIR}/suite.rc"
cylc reload "${CYLC_WORKFLOW_ID}"
cylc trigger "${CYLC_WORKFLOW_ID}//1/foo"
