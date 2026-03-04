# Big Work: Delegate, Don't Read

When implementation work touches 3+ files or involves files over 200 lines, delegate to subagents instead of reading everything into your context. Your context is finite — files survive on disk, context does not.

Use `superpowers:dispatching-parallel-agents` for independent tasks, `superpowers:subagent-driven-development` for plan-based execution, or `superpowers:executing-plans` for sequential work with review checkpoints.
