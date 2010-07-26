Small dummy-mode system to test use of suicide and conditional prerequisites:

TaskA represents a warm-cycled forecast model.
PostA represents post-processing for TaskA

Recovery is a special forecast to run when A fails (behind it may be,
for example, the same forecast model configured to run with a shorter
timestep to avoid numerical instability). It generates the same output
for post processing as A.

If A finishes, recovery self-destructs.

If A aborts, recovery runs.

If recovery finishes, A self-destructs.

PostA triggers off A or Recovery.
