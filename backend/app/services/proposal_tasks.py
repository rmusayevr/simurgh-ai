"""
Proposal Celery Tasks.

Contains Celery tasks for async proposal generation.
"""

from sqlmodel import select
import structlog
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.core.celery_app import celery_app
from app.models.proposal import (
    AgentPersona,
    Proposal,
    ProposalStatus,
    ProposalVariation,
)
from app.services.ai import proposal_generation_service
from app.db.session import get_sync_session

logger = structlog.get_logger()


@celery_app.task(name="generate_proposal_content")
def generate_proposal_content_task(proposal_id: int):
    """
    Celery task to generate 3 DISTINCT proposal variations from AI Council debate.

    RESEARCH WORKFLOW:
        Phase 1: Conduct debate (3 personas discuss)
        Phase 2: Generate 3 SEPARATE proposals (one per persona)
        Phase 3: Human selects winning proposal

    Flow:
        1. Sync DB prep — fetch proposal, check feature flags, build RAG context
        2. Async AI generation — conduct debate + generate 3 proposals
        3. Save 3 ProposalVariation records (legacy_keeper, innovator, mediator)
        4. Mark proposal COMPLETED or FAILED
    """
    log = logger.bind(task="generate_proposal", proposal_id=proposal_id)

    log.info("task_started")

    s_gen = get_sync_session()
    sess = next(s_gen)

    try:
        proposal = sess.get(Proposal, proposal_id)
        if not proposal:
            log.error("proposal_not_found")
            return

        # Check feature flag
        from app.models.settings import SystemSettings

        system_settings = sess.exec(select(SystemSettings)).first()
        if not (system_settings and system_settings.debate_feature_enabled):
            log.info("ai_council_disabled")
            proposal.mark_failed("AI Council is currently disabled")
            sess.add(proposal)
            sess.commit()
            return

        # Mark as PROCESSING
        proposal.status = ProposalStatus.PROCESSING
        sess.add(proposal)
        sess.commit()

        # Build RAG context
        from app.models.chunk import DocumentChunk
        from app.models.project import Project, HistoricalDocument
        from app.models.stakeholder import Stakeholder

        project = sess.exec(
            select(Project).where(Project.id == proposal.project_id)
        ).first()
        if not project:
            log.error("project_not_found")
            return

        # DocumentChunk links to HistoricalDocument, not Project directly
        doc_ids = sess.exec(
            select(HistoricalDocument.id).where(
                HistoricalDocument.project_id == project.id
            )
        ).all()

        chunk_texts = []
        if doc_ids:
            chunks = sess.exec(
                select(DocumentChunk)
                .where(DocumentChunk.document_id.in_(doc_ids))
                .limit(20)
            ).all()
            chunk_texts = [c.content for c in chunks if c.content]

        # Get task documents
        from app.models.proposal import TaskDocument

        task_docs = sess.exec(
            select(TaskDocument).where(TaskDocument.proposal_id == proposal_id)
        ).all()
        task_doc_texts = [d.content_text for d in task_docs if d.content_text]

        # Get stakeholders directly by project
        stakeholder_records = sess.exec(
            select(Stakeholder).where(Stakeholder.project_id == project.id)
        ).all()
        stakeholders = [
            {
                "name": s.name,
                "role": s.role,
                "department": s.department,
                "concerns": s.notes,
            }
            for s in stakeholder_records
        ]

        log.info(
            "rag_context_built",
            chunks=len(chunk_texts),
            task_docs=len(task_doc_texts),
            stakeholders=len(stakeholders),
        )

        # Get active model
        active_model = system_settings.ai_model or "claude-sonnet-4-20250514"

        log.info("calling_ai_council_for_3_proposals", model=active_model)

        import asyncio

        async def run_async():
            local_engine = create_async_engine(
                str(settings.DATABASE_URL), echo=False, future=True
            )

            from sqlmodel.ext.asyncio.session import AsyncSession

            async with AsyncSession(local_engine) as async_session:
                try:
                    log.info("calling_ai_council_for_3_proposals", model=active_model)

                    try:
                        variations_data = (
                            await proposal_generation_service.generate_three_proposals(
                                session=async_session,
                                task=proposal.task_description,
                                context_chunks=chunk_texts,
                                task_docs=task_doc_texts,
                                stakeholders=stakeholders,
                                model=active_model,
                                use_caching=True,
                                proposal_id=proposal_id,
                                acting_user_id=proposal.created_by_id,
                            )
                        )
                    except Exception as gen_err:
                        import traceback

                        print(
                            f"[GENERATE_THREE_PROPOSALS ERROR] {type(gen_err).__name__}: {gen_err}"
                        )
                        print(traceback.format_exc())
                        raise

                    log.info(
                        "generate_three_proposals_returned",
                        result_type=type(variations_data).__name__,
                        result_count=len(variations_data) if variations_data else 0,
                    )

                    if not variations_data or len(variations_data) != 3:
                        log.warning(
                            "incorrect_variation_count",
                            count=len(variations_data) if variations_data else 0,
                        )
                        return None

                    async_proposal = await async_session.get(Proposal, proposal_id)
                    if not async_proposal:
                        log.error("proposal_not_found_on_async_session")
                        return None

                    log.info("saving_3_distinct_variations")

                    existing_stmt = select(ProposalVariation).where(
                        ProposalVariation.proposal_id == proposal_id
                    )
                    existing_result = await async_session.exec(existing_stmt)
                    existing_variations = existing_result.all()
                    for ev in existing_variations:
                        await async_session.delete(ev)
                    if existing_variations:
                        await async_session.flush()
                        log.info(
                            "existing_variations_cleared",
                            count=len(existing_variations),
                        )

                    for v_data in variations_data:
                        persona_str = v_data.get("persona", "")
                        try:
                            persona = AgentPersona(persona_str.upper())
                        except ValueError:
                            log.warning("unknown_persona", persona=persona_str)
                            persona = AgentPersona.MEDIATOR

                        variation = ProposalVariation(
                            proposal_id=async_proposal.id,
                            agent_persona=persona,
                            structured_prd=v_data.get("structured_prd", ""),
                            reasoning=v_data.get("reasoning", ""),
                            trade_offs=v_data.get("trade_offs", ""),
                            confidence_score=v_data.get("confidence_score", 0),
                        )
                        async_session.add(variation)

                    await async_session.commit()
                    log.info("variations_saved", count=len(variations_data))

                    final_proposal = await async_session.get(Proposal, proposal_id)
                    if final_proposal:
                        final_proposal.status = ProposalStatus.COMPLETED
                        await async_session.commit()
                        log.info("proposal_completed", proposal_id=proposal_id)

                except Exception as e:
                    log.error("async_proposal_generation_failed", error=str(e))
                    await async_session.rollback()
                    raise

        asyncio.run(run_async())

    except Exception as e:
        log.error("task_failed", error=str(e))

        s_gen = get_sync_session()
        sess = next(s_gen)
        p = sess.get(Proposal, proposal_id)
        if p:
            p.mark_failed(f"Critical task failure: {str(e)}")
            sess.add(p)
            sess.commit()
        sess.close()
