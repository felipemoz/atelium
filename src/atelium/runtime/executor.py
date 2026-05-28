from __future__ import annotations
import asyncio
import logging
import time
from uuid import UUID

from ..manifest.schema import AgentManifest, IrreversibilityRequires
from ..config import settings
from ..core.models import (
    Step, Pipeline, PipelineStatus, StepStatus, GuardAction,
)
from ..core.transition_guard import TransitionGuardEngine
from ..core.self_healing import SelfHealingLoop
from ..core.saga import SagaCoordinator
from ..core.state import StepStateManager
from ..infra import publish

logger = logging.getLogger(__name__)


class AgentExecutor:
    """
    Executes a single Step against an agent manifest.
    Handles the full resilience loop: LLM call → guard → self-heal → HITL → SAGA.
    """

    def __init__(
        self,
        state_manager: StepStateManager,
        llm_client=None,      # OllamaClient or LangChain-compatible
        mcp_executor=None,    # MCPExecutor for tool calls
        hitl_approver=None,   # HITLApprover for human-in-the-loop
        router=None,          # EmergentRouter for dynamic delegation
    ):
        self._state = state_manager
        self._llm = llm_client
        self._mcp = mcp_executor
        self._hitl = hitl_approver
        self._router = router

        self._guard = TransitionGuardEngine()
        self._healer = SelfHealingLoop()
        self._saga = SagaCoordinator()

    async def execute_step(self, step: Step, manifest: AgentManifest) -> Step:
        step.mark_started()
        await self._state.save_step(step)

        # Build initial messages from task prompt + context window
        messages = self._build_messages(step, manifest)

        # Resilience loop
        while step.iteration <= manifest.spec.task.self_healing.max_iterations:
            step = await self._invoke_llm(step, manifest, messages)
            await self._state.save_step(step)

            if step.status == StepStatus.FAILED:
                # LLM hard failure — escalate immediately
                break

            guard_result = self._guard.evaluate(step, manifest)

            if guard_result.passed:
                step.status = StepStatus.SUCCEEDED
                await self._saga_register(step, manifest)
                await self._state.save_step(step)
                await publish("atelium.step.completed", {
                    "pipeline_id": str(step.pipeline_id),
                    "step_id": str(step.step_id),
                    "status": step.status.value,
                })
                return step

            action = guard_result.action

            if action == GuardAction.SELF_HEAL:
                messages = self._healer.build_feedback_messages(
                    step, guard_result, manifest, messages
                )
                step = self._healer.prepare_step_for_retry(step)
                await self._state.save_step(step)
                continue

            if action == GuardAction.HITL:
                step = await self._handle_hitl(step, guard_result, manifest)
                if step.status == StepStatus.SUCCEEDED:
                    return step
                break

            if action == GuardAction.COMPENSATE:
                break  # caller handles compensation

            if action == GuardAction.CIRCUIT_BREAK:
                if self._router:
                    self._router.open_circuit(
                        step.agent_name,
                        settings.circuit_breaker_timeout_ms,
                    )
                step.mark_failed(guard_result.error_messages())
                break

            if action == GuardAction.ABORT:
                step.mark_failed(["Pipeline aborted by failure_criteria rule"])
                break

        if step.status not in (StepStatus.SUCCEEDED, StepStatus.WAITING_HITL):
            step.mark_failed(step.validation_errors or ["Max iterations exceeded"])

        await self._state.save_step(step)
        return step

    # ------------------------------------------------------------------
    # LLM invocation
    # ------------------------------------------------------------------

    async def _invoke_llm(
        self, step: Step, manifest: AgentManifest, messages: list[dict]
    ) -> Step:
        model_spec = manifest.spec.model
        t0 = time.monotonic()
        try:
            if self._mcp and manifest.spec.mcps:
                output, usage = await self._mcp.execute_with_tools(
                    model=model_spec.name,
                    messages=messages,
                    mcps=manifest.spec.mcps,
                    temperature=model_spec.temperature,
                    max_tokens=model_spec.max_tokens,
                )
            elif self._llm:
                resp = await self._llm.chat(
                    model=model_spec.name,
                    messages=messages,
                    temperature=model_spec.temperature,
                    max_tokens=model_spec.max_tokens,
                )
                output = _parse_llm_response(resp)
                usage = resp.get("eval_count", 0)
            else:
                # Stub for testing
                output = {"_stub": True}
                usage = 0

            step.output = output
            step.tokens_used = usage
            elapsed = int((time.monotonic() - t0) * 1000)
            step.elapsed_ms = elapsed
        except Exception as exc:
            logger.error("LLM invocation failed for step %s: %s", step.step_id, exc)
            step.mark_failed([f"LLM error: {exc}"])
        return step

    # ------------------------------------------------------------------
    # HITL
    # ------------------------------------------------------------------

    async def _handle_hitl(self, step: Step, guard_result, manifest: AgentManifest) -> Step:
        step.status = StepStatus.WAITING_HITL
        await self._state.save_step(step)

        await publish("atelium.hitl.gate", {
            "pipeline_id": str(step.pipeline_id),
            "step_id": str(step.step_id),
            "errors": guard_result.error_messages(),
        })

        if self._hitl:
            try:
                decision = await asyncio.wait_for(
                    self._hitl.wait_for_decision(step.step_id),
                    timeout=settings.hitl_timeout_ms / 1000,
                )
                if decision.get("approved"):
                    step.output = decision.get("output", step.output)
                    step.status = StepStatus.SUCCEEDED
                else:
                    step.mark_failed(["Rejected by human reviewer"])
            except asyncio.TimeoutError:
                step.mark_failed(["HITL timeout exceeded"])
        else:
            step.mark_failed(["HITL required but no approver configured"])

        return step

    # ------------------------------------------------------------------
    # SAGA registration
    # ------------------------------------------------------------------

    async def _saga_register(self, step: Step, manifest: AgentManifest) -> None:
        pipeline = Pipeline(manifest_name=manifest.metadata.name)
        pipeline.pipeline_id = step.pipeline_id
        self._saga.register_step(pipeline, step, manifest)

    # ------------------------------------------------------------------
    # Message builder
    # ------------------------------------------------------------------

    def _build_messages(self, step: Step, manifest: AgentManifest) -> list[dict]:
        task = manifest.spec.task
        system_prompt = task.prompt_template.format(**step.input)

        context_parts = []
        for summary in step.context_window:
            context_parts.append(
                f"[{summary.agent_name}] {summary.summary}: {summary.output_fields}"
            )

        messages: list[dict] = []
        if context_parts:
            messages.append({
                "role": "system",
                "content": system_prompt + "\n\nContext from previous steps:\n" + "\n".join(context_parts),
            })
        else:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": _format_input(step.input)})
        return messages


def _parse_llm_response(resp: dict) -> dict:
    """Extract structured output from Ollama chat response."""
    import json
    content = resp.get("message", {}).get("content", "")
    # Try JSON extraction
    try:
        # Look for ```json block
        if "```json" in content:
            start = content.index("```json") + 7
            end = content.index("```", start)
            return json.loads(content[start:end].strip())
        # Try bare JSON
        return json.loads(content.strip())
    except (ValueError, KeyError):
        return {"raw_output": content}


def _format_input(inp: dict) -> str:
    import json
    return json.dumps(inp, ensure_ascii=False, indent=2)
