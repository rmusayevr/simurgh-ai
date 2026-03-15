/**
 * Experiment scenario configuration.
 *
 * HOW TO SET UP BEFORE A STUDY SESSION:
 * ─────────────────────────────────────
 * 1. Run: docker compose exec backend python -m app.db.seed_scenarios
 * 2. The script prints the created proposal IDs for each scenario.
 * 3. Copy those IDs into the `proposalId` fields below — one per scenario.
 * 4. Save this file and rebuild the frontend (or let Vite hot-reload in dev).
 *
 * The proposalId is used to fetch baseline and multi-agent proposals
 * from the database during the experiment session.
 *
 * EXAMPLE output from seed_scenarios:
 *   Scenario A (Payment Migration)      → proposal_id: 12
 *   Scenario B (Analytics Pipeline)     → proposal_id: 13
 *   Scenario C (Auth Modernisation)     → proposal_id: 14
 *   Scenario D (Media Storage Scaling)  → proposal_id: 15
 */

export interface ScenarioConfig {
    id: number;
    title: string;
    description: string;
    /** Proposal ID printed by seed_scenarios.py — update before each study session */
    proposalId: number;
}

export const EXPERIMENT_SCENARIOS: ScenarioConfig[] = [
    {
        id: 1,
        title: 'Scenario A: Payment Service Migration',
        description:
            "Your company's e-commerce platform processes all payments inside a 6-year-old Rails monolith. " +
            'Three Black Friday outages last year cost an estimated €280 k in lost revenue — the payment ' +
            'flow cannot scale independently of the rest of the application. ' +
            'You need to recommend an architecture for migrating payment processing out of the monolith ' +
            'within 6 months while maintaining PCI-DSS Level 1 compliance and zero data loss. ' +
            'Options include extracting a dedicated microservice, introducing a queue/caching layer ' +
            'in front of the existing code, or adopting a third-party payment orchestration platform.',
        proposalId: 1, // ← Replace with ID printed by seed_scenarios.py
    },
    {
        id: 2,
        title: 'Scenario B: Real-Time Analytics Pipeline',
        description:
            'Your SaaS product dashboard queries a 2 TB PostgreSQL database directly for all analytics. ' +
            'As you approach 500 business customers, dashboard load times have degraded from 2 s to 18–45 s, ' +
            'and the read replica hits 95 % CPU during business hours. ' +
            'You need a recommendation for a real-time analytics pipeline that ingests ~8 million events/day ' +
            '(projected 10× growth in 12 months), serves dashboard metrics with under 5 s latency, ' +
            'and supports ad-hoc SQL queries from the data team — all within €15 k/month additional cloud spend.',
        proposalId: 2, // ← Replace with ID printed by seed_scenarios.py
    },
    {
        id: 3,
        title: 'Scenario C: Authentication Modernisation',
        description:
            'Your platform authenticates 520 000 active users with a custom PHP session system built in 2018. ' +
            'Three upcoming product changes — a native mobile app, a scoped developer API, and enterprise SSO ' +
            'for 40 business accounts — cannot be delivered with the current auth architecture. ' +
            'Recommend an approach that modernises authentication and authorisation without forcing any of the ' +
            '520 000 existing users to re-authenticate, maintains GDPR compliance, and can be delivered ' +
            'within 9 months with a team of 6 engineers.',
        proposalId: 3, // ← Replace with ID printed by seed_scenarios.py
    },
    {
        id: 4,
        title: 'Scenario D: Media Storage Scaling',
        description:
            'Your platform stores user-generated photos, videos, and documents on a 48 TB NAS cluster ' +
            'that is 87 % full — at current growth of ~800 GB/week, capacity runs out in under 4 months. ' +
            'Approximately 9 million public media URLs of the form ' +
            'https://media.ourplatform.com/{uuid}/{filename} exist in customer integrations and ' +
            'must continue to resolve without redirects after any migration. ' +
            'Recommend a storage architecture that handles 10 TB+ annual growth, stays within a ' +
            '€50 k first-year budget, and can be executed by a 3-person team with no planned downtime.',
        proposalId: 4, // ← Replace with ID printed by seed_scenarios.py
    },
];

/** Returns the scenario assigned to a participant based on their ID (deterministic, balanced). */
export function pickScenario(participantId: number): ScenarioConfig {
    const idx = participantId % EXPERIMENT_SCENARIOS.length;
    return EXPERIMENT_SCENARIOS[idx];
}