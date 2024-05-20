The workflow-state command and the workflow-state xtrigger now take univeral IDs
instead of separate arguments for cycle point, task name, etc. 

The Cylc 7 suite_state xtrigger is still supported, with separate arguments, but 
is deprecated.

Automatic workflow state polling tasks (via special graph syntax) are still
supported, but deprecated: use the workflow_state xtrigger instead.

The owner and host arguments are no longer supported, for workflow state polling.
To poll another user's workflow you must be able to see their run directory.
