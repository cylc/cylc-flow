#!/bin/bash

# Change "script = false" -> "true" in 1/foo, then reload and retrigger it.

if grep "\[command\] reload_workflow" "${CYLC_WORKFLOW_LOG_DIR}/log" >/dev/null; then
    # Abort if not the first call (avoid an endless loop if the reload does not
    # have the intended effect).
    cylc stop --now --now "${CYLC_WORKFLOW_ID}"
    exit 1
fi
sed -i "s/false/true/" "${CYLC_WORKFLOW_RUN_DIR}/flow.cylc"
cylc reload "${CYLC_WORKFLOW_ID}"
cylc trigger "${CYLC_WORKFLOW_ID}//1/foo"
