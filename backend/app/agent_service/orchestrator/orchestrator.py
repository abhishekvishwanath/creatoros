"""Orchestrator (CLAUDE.md §9): answers "what should happen next" for a single
agent invocation — creates the observability record, runs the agent, and
makes sure a failure never leaves a run looking like it silently succeeded
(CLAUDE.md §43). It does not apply proposed state changes itself; that stays
in the application-service layer (see app/api/routes/creators.py) which
decides how to interpret each change type via a domain state service.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_service.model_router.router import ModelRouter
from app.agent_service.schemas.contracts import AgentOutput
from app.core.ids import generate_id
from app.domain.agents.models import AgentMessage, AgentRun
from app.schemas.creator import CreatorStateSnapshot


class Orchestrator:
    def __init__(self, db: AsyncSession, model_router: ModelRouter):
        self.db = db
        self.model_router = model_router

    async def run_agent(
        self,
        *,
        agent,
        creator_id: str,
        workflow_name: str,
        context: CreatorStateSnapshot,
        **extra_context,
    ) -> AgentOutput:
        run = AgentRun(
            id=generate_id("agent_run"),
            creator_id=creator_id,
            agent_name=agent.name,
            workflow_name=workflow_name,
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        await self.db.flush()

        try:
            output = await agent.run(context, self.model_router, **extra_context)
            run.status = "succeeded" if output.status != "failed" else "failed"
            run.state_changes = {
                "proposed_state_changes": output.proposed_state_changes,
                "warnings": output.warnings,
            }
            # run.error is reserved for run-level failures (CLAUDE.md §44 observability) —
            # an agent that succeeds with caveats belongs in state_changes.warnings above,
            # not here, or monitoring that filters on error IS NOT NULL would flag every
            # successful stub run (no ANTHROPIC_API_KEY) as an error.
            if output.status == "failed" and output.warnings:
                run.error = "; ".join(output.warnings)
        except Exception as exc:  # noqa: BLE001 - convert any agent failure into a safe AgentOutput
            run.status = "failed"
            run.error = str(exc)
            output = AgentOutput(
                status="failed",
                summary=f"{agent.name} raised an unexpected error.",
                confidence=0.0,
                warnings=[str(exc)],
            )
        finally:
            run.ended_at = datetime.now(timezone.utc)
            run.duration_ms = int((run.ended_at - run.started_at).total_seconds() * 1000)
            self.db.add(
                AgentMessage(
                    id=generate_id("agent_message"),
                    agent_run_id=run.id,
                    role="assistant",
                    content=output.summary,
                )
            )
            await self.db.flush()

        return output
