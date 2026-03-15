from sqlmodel import SQLModel


class IntegrationBase(SQLModel):
    provider: str  # "jira" or "confluence"
    base_url: str
    username: str


class IntegrationCreate(IntegrationBase):
    api_token: str


class IntegrationRead(IntegrationBase):
    id: int
    project_id: int
