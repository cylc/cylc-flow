CYCLING DAEMON TASK exploratory notes

A download task (or similar) probably should not be part of a cylc
suite because it should keep going, downloading data when available,
even when the cylc suite has been shut down.

However, one or more daemon tasks could still be used to tell other
tasks what data is available already locally, instead of one or more
spawning contact tasks for the same purpose.

TASK PROXY:
* Accumulate outputs, but discard any older than the oldest potentially
useful one (similar to deletion of normal tasks)?

EXTERNAL TASK:
* an initial cycle time determines initial action?
* use a lock to prevent duplication at restart?

