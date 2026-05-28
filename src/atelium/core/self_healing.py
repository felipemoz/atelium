from __future__ import annotations

from ..manifest.schema import AgentManifest
from .models import Step, StepStatus, GuardResult


class SelfHealingLoop:
    """Builds a feedback prompt and returns updated messages for LLM re-invocation."""

    def build_feedback_messages(
        self,
        step: Step,
        guard_result: GuardResult,
        manifest: AgentManifest,
        original_messages: list[dict],
    ) -> list[dict]:
        task = manifest.spec.task
        sh = task.self_healing

        validation_errors = "\n".join(
            f"- {fc.field}: expected {fc.expected}, got {fc.actual!r}"
            for fc in guard_result.failed_criteria
        )
        success_criteria = "\n".join(
            f"- {c.field} ({c.type})"
            + (f": one of {c.values}" if c.values else "")
            + (f": >= {c.min}" if c.min is not None else "")
            for c in task.success_criteria
        )
        failed_fields = ", ".join(fc.field for fc in guard_result.failed_criteria)

        feedback = sh.feedback_template.format(
            validation_errors=validation_errors,
            success_criteria=success_criteria,
            failed_fields=failed_fields,
        )

        import json
        messages = list(original_messages)
        if step.output is not None:
            messages.append({"role": "assistant", "content": json.dumps(step.output)})
        messages.append({"role": "user", "content": feedback})

        return messages

    def prepare_step_for_retry(self, step: Step) -> Step:
        step.iteration += 1
        step.status = StepStatus.SELF_HEALING
        step.validation_errors = []
        step.output = None
        return step
