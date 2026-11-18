"""
Submission signals.

Contest scoring used to run from a post_save receiver here, which re-scored a
submission on *every* save of a terminal row (duplicate judge callbacks,
admin edits) and double-counted wrong attempts. Verdict side effects now run
exactly once from apps.submissions.services.finalize_submission(), called in
the same transaction as the terminal state transition.

This module is still imported by SubmissionsConfig.ready(); keep new receivers
idempotent.
"""
