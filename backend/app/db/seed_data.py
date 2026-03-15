import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.db.session import engine
from app.models.user import User, UserRole
from app.models.project import Project
from app.models.links import ProjectStakeholderLink, ProjectRole
from app.models.stakeholder import Stakeholder, InfluenceLevel, InterestLevel, Sentiment
from app.models.prompt import PromptTemplate
from app.core.security import hash_password


async def seed_data():
    async with AsyncSession(engine, expire_on_commit=False) as session:
        # ==========================================
        # 1. USERS
        # ==========================================
        print("Creating users...")
        users_to_create = [
            {
                "email": "admin@example.com",
                "name": "System Admin",
                "role": UserRole.ADMIN,
                "is_superuser": True,
            },
            {
                "email": "director@example.com",
                "name": "Studio Director",
                "role": UserRole.ADMIN,
                "is_superuser": True,
            },
            {
                "email": "manager.loft@example.com",
                "name": "Loft Project Lead",
                "role": UserRole.MANAGER,
                "is_superuser": True,
            },
            {
                "email": "manager.eco@example.com",
                "name": "Sustainability Lead",
                "role": UserRole.MANAGER,
                "is_superuser": False,
            },
            {
                "email": "architect.1@example.com",
                "name": "Senior Architect",
                "role": UserRole.USER,
                "is_superuser": False,
            },
            {
                "email": "architect.2@example.com",
                "name": "Junior Designer",
                "role": UserRole.USER,
                "is_superuser": False,
            },
            {
                "email": "intern@example.com",
                "name": "Drafting Intern",
                "role": UserRole.USER,
                "is_superuser": False,
            },
            {
                "email": "external.consultant@example.com",
                "name": "Safety Specialist",
                "role": UserRole.USER,
                "is_superuser": False,
            },
        ]

        db_users = {}
        for u in users_to_create:
            stmt = select(User).where(User.email == u["email"])
            existing = (await session.execute(stmt)).scalars().first()
            if not existing:
                user = User(
                    email=u["email"],
                    hashed_password=hash_password("password123"),
                    full_name=u["name"],
                    role=u["role"],
                    is_active=True,
                    is_superuser=u.get("is_superuser", False),
                    email_verified=True,
                )
                session.add(user)
                db_users[u["email"]] = user
            else:
                existing.role = u["role"]
                existing.is_superuser = u.get("is_superuser", False)
                existing.is_active = True
                existing.email_verified = True
                session.add(existing)
                db_users[u["email"]] = existing
        await session.commit()

        # ==========================================
        # 2. PROJECTS
        # ==========================================
        print("Initializing projects...")
        projects_data = [
            {
                "name": "Modern Loft Conversion",
                "desc": "Warehouse attic renovation.",
                "owner_email": "manager.loft@example.com",
            },
            {
                "name": "Kitchen Expansion - Villa 7",
                "desc": "Structural kitchen extension.",
                "owner_email": "manager.loft@example.com",
            },
            {
                "name": "Eco-Friendly Terrace Update",
                "desc": "Sustainable outdoor living space.",
                "owner_email": "manager.eco@example.com",
            },
        ]
        db_projects = []
        for p in projects_data:
            stmt = select(Project).where(Project.name == p["name"])
            existing_p = (await session.execute(stmt)).scalars().first()
            if not existing_p:
                owner = db_users.get(p["owner_email"], list(db_users.values())[0])
                proj = Project(
                    name=p["name"],
                    description=p["desc"],
                    owner_id=owner.id,
                    member_count=1,
                )
                session.add(proj)
                db_projects.append((proj, owner))
            else:
                owner = db_users.get(p["owner_email"], list(db_users.values())[0])
                db_projects.append((existing_p, owner))
        await session.commit()

        # ==========================================
        # 2b. OWNER LINKS
        # Create ProjectStakeholderLink OWNER records for each project's owner.
        # Without this, the owner cannot manage members (403 Forbidden) because
        # assert_can_manage() looks up the link table for non-ADMIN system roles.
        # ==========================================
        print("Creating owner membership links...")
        for proj, owner in db_projects:
            # Refresh to ensure proj.id is populated after commit
            await session.refresh(proj)
            stmt = select(ProjectStakeholderLink).where(
                ProjectStakeholderLink.project_id == proj.id,
                ProjectStakeholderLink.user_id == owner.id,
            )
            existing_link = (await session.execute(stmt)).scalars().first()
            if not existing_link:
                owner_link = ProjectStakeholderLink(
                    project_id=proj.id,
                    user_id=owner.id,
                    role=ProjectRole.OWNER,
                )
                session.add(owner_link)
        await session.commit()

        # ==========================================
        # 3. STAKEHOLDERS
        # ==========================================
        print("Creating 18 stakeholders...")

        # Unwrap project objects from tuples
        p1 = db_projects[0][0]
        p2 = db_projects[1][0]
        p3 = db_projects[2][0]

        p1_id = p1.id
        p2_id = p2.id
        p3_id = p3.id

        all_stakeholders = [
            # Project 1: Modern Loft
            (
                p1_id,
                "Alice Thompson",
                "Homeowner",
                "Client",
                InfluenceLevel.HIGH,
                InterestLevel.HIGH,
                Sentiment.CHAMPION,
            ),
            (
                p1_id,
                "Bob Builder",
                "General Contractor",
                "Construction",
                InfluenceLevel.HIGH,
                InterestLevel.MEDIUM,
                Sentiment.NEUTRAL,
            ),
            (
                p1_id,
                "Charlie Check",
                "Building Inspector",
                "Regulatory",
                InfluenceLevel.HIGH,
                InterestLevel.LOW,
                Sentiment.CONCERNED,
            ),
            (
                p1_id,
                "David Noise",
                "Adjoining Resident",
                "Neighbors",
                InfluenceLevel.MEDIUM,
                InterestLevel.HIGH,
                Sentiment.RESISTANT,
            ),
            (
                p1_id,
                "Eve Design",
                "Interior Designer",
                "Consultant",
                InfluenceLevel.LOW,
                InterestLevel.HIGH,
                Sentiment.SUPPORTIVE,
            ),
            (
                p1_id,
                "Frank Fire",
                "Fire Safety Marshall",
                "Regulatory",
                InfluenceLevel.HIGH,
                InterestLevel.LOW,
                Sentiment.BLOCKER,
            ),
            # Project 2: Kitchen Expansion
            (
                p2_id,
                "Gary Gastronomy",
                "Client",
                "Client",
                InfluenceLevel.HIGH,
                InterestLevel.HIGH,
                Sentiment.CHAMPION,
            ),
            (
                p2_id,
                "Harriet Pipe",
                "Plumbing Subcontractor",
                "Trades",
                InfluenceLevel.MEDIUM,
                InterestLevel.MEDIUM,
                Sentiment.NEUTRAL,
            ),
            (
                p2_id,
                "Ian Iron",
                "Steel Fabricator",
                "Suppliers",
                InfluenceLevel.MEDIUM,
                InterestLevel.LOW,
                Sentiment.SUPPORTIVE,
            ),
            (
                p2_id,
                "Jenny Joint",
                "Homeowner's Spouse",
                "Client",
                InfluenceLevel.MEDIUM,
                InterestLevel.HIGH,
                Sentiment.CONCERNED,
            ),
            (
                p2_id,
                "Kevin Kwatt",
                "Electrical Engineer",
                "Engineering",
                InfluenceLevel.HIGH,
                InterestLevel.MEDIUM,
                Sentiment.SUPPORTIVE,
            ),
            (
                p2_id,
                "Laura Law",
                "Zoning Officer",
                "Regulatory",
                InfluenceLevel.HIGH,
                InterestLevel.LOW,
                Sentiment.NEUTRAL,
            ),
            # Project 3: Eco-Terrace
            (
                p3_id,
                "Mark Nature",
                "Landscape Architect",
                "Design",
                InfluenceLevel.HIGH,
                InterestLevel.HIGH,
                Sentiment.CHAMPION,
            ),
            (
                p3_id,
                "Nancy Nextdoor",
                "Neighbor",
                "Neighbors",
                InfluenceLevel.LOW,
                InterestLevel.HIGH,
                Sentiment.RESISTANT,
            ),
            (
                p3_id,
                "Oscar Organic",
                "Sustainability Auditor",
                "Regulatory",
                InfluenceLevel.MEDIUM,
                InterestLevel.MEDIUM,
                Sentiment.SUPPORTIVE,
            ),
            (
                p3_id,
                "Paula Plant",
                "Nursery Supplier",
                "Suppliers",
                InfluenceLevel.LOW,
                InterestLevel.LOW,
                Sentiment.SUPPORTIVE,
            ),
            (
                p3_id,
                "Quincy Quake",
                "Soil Specialist",
                "Engineering",
                InfluenceLevel.HIGH,
                InterestLevel.MEDIUM,
                Sentiment.NEUTRAL,
            ),
            (
                p3_id,
                "Rita Render",
                "3D Visualizer",
                "Marketing",
                InfluenceLevel.LOW,
                InterestLevel.HIGH,
                Sentiment.SUPPORTIVE,
            ),
        ]

        for pid, name, role, dept, infl, intr, sent in all_stakeholders:
            stmt = select(Stakeholder).where(
                Stakeholder.name == name, Stakeholder.project_id == pid
            )
            if not (await session.execute(stmt)).scalars().first():
                session.add(
                    Stakeholder(
                        name=name,
                        role=role,
                        department=dept,
                        project_id=pid,
                        influence=infl,
                        interest=intr,
                        sentiment=sent,
                    )
                )
        await session.commit()

        # ==========================================
        # 4. AI PERSONAS (PROMPT TEMPLATES)
        # Slugs MUST match debate_service.TURN_ORDER:
        #   legacy_keeper, innovator, mediator
        # Category MUST be TemplateCategory.DEBATE so persona_service finds them.
        # ==========================================
        print("Seeding Council of Agents persona prompt templates...")

        from app.models.prompt import TemplateCategory
        from app.services.persona_service import PersonaService

        # Reuse the canonical prompts from PersonaService to keep a single source of truth
        _fallbacks = PersonaService._FALLBACK_PROMPTS

        prompts_to_create = [
            PromptTemplate(
                name="Legacy Keeper",
                slug="legacy_keeper",
                category=TemplateCategory.DEBATE,
                description="Risk-averse principal architect. Prioritises stability, security, and maintainability.",
                system_prompt=_fallbacks["legacy_keeper"],
                is_active=True,
            ),
            PromptTemplate(
                name="Innovator",
                slug="innovator",
                category=TemplateCategory.DEBATE,
                description="Cloud-native advocate. Prioritises scalability, velocity, and modern tooling.",
                system_prompt=_fallbacks["innovator"],
                is_active=True,
            ),
            PromptTemplate(
                name="Mediator",
                slug="mediator",
                category=TemplateCategory.DEBATE,
                description="Pragmatic principal engineer. Synthesises both perspectives into phased, actionable plans.",
                system_prompt=_fallbacks["mediator"],
                is_active=True,
            ),
        ]

        for p in prompts_to_create:
            stmt = select(PromptTemplate).where(PromptTemplate.slug == p.slug)
            existing = (await session.execute(stmt)).scalars().first()
            if not existing:
                session.add(p)
            else:
                # Update existing prompt to ensure fixes are applied
                existing.system_prompt = p.system_prompt
                session.add(existing)

        await session.commit()

        print(
            "Successfully seeded Users, Projects, Stakeholders, Owner Links, and AI Personas."
        )


if __name__ == "__main__":
    asyncio.run(seed_data())
