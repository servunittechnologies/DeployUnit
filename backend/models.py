"""Pydantic models for SaaS platform."""
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime, timezone
import uuid


def _id() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ============ Auth ============
class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    name: str = Field(min_length=1, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    email: str
    name: str
    role: str = "user"
    github_login: Optional[str] = None
    github_avatar_url: Optional[str] = None
    created_at: datetime


# ============ Workspace ============
class WorkspaceIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: Literal["solo", "agency"] = "solo"


class WorkspaceOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    name: str
    slug: str
    type: str
    owner_id: str
    plan: str = "free"
    created_at: datetime


class WorkspaceMemberIn(BaseModel):
    email: EmailStr
    role: Literal["admin", "developer", "billing", "viewer"] = "developer"


# ============ Project ============
class ProjectIn(BaseModel):
    workspace_id: str
    name: str = Field(min_length=1, max_length=80)
    description: Optional[str] = ""


class ProjectOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    workspace_id: str
    name: str
    slug: str
    description: str = ""
    created_at: datetime


# ============ App ============
class AppIn(BaseModel):
    workspace_id: str
    project_id: Optional[str] = None
    name: str = Field(min_length=1, max_length=80)
    framework: Literal["nextjs", "node", "static"] = "nextjs"
    repo_url: str
    branch: str = "main"
    build_command: Optional[str] = None
    start_command: Optional[str] = None
    env_vars: Dict[str, str] = Field(default_factory=dict)
    environment: Literal["production", "staging"] = "production"
    paired_app_id: Optional[str] = None  # link to counterpart on create


class AppOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    workspace_id: str
    project_id: Optional[str] = None
    name: str
    slug: str
    framework: str
    repo_url: str
    branch: str
    build_command: Optional[str] = None
    start_command: Optional[str] = None
    env_vars: Dict[str, str] = Field(default_factory=dict)
    coolify_app_uuid: Optional[str] = None
    status: str = "queued"
    last_deploy_at: Optional[datetime] = None
    primary_url: Optional[str] = None
    auto_deploy: bool = True
    tier: Literal["development", "production"] = "development"
    protected_branches: List[str] = Field(default_factory=lambda: ["main"])
    created_at: datetime


class AppUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    branch: Optional[str] = None
    build_command: Optional[str] = None
    start_command: Optional[str] = None
    auto_deploy: Optional[bool] = None
    project_id: Optional[str] = None
    tier: Optional[Literal["development", "production"]] = None
    protected_branches: Optional[List[str]] = None


class EnvVarUpdate(BaseModel):
    env_vars: Dict[str, str]


class RedeployIn(BaseModel):
    branch: Optional[str] = None
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None


# ============ Deployment ============
class DeploymentOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    app_id: str
    workspace_id: str
    status: str
    commit_sha: Optional[str] = None
    commit_message: Optional[str] = None
    branch: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
    coolify_deployment_uuid: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None


# ============ Domain ============
class DomainIn(BaseModel):
    app_id: str
    domain: str


class DomainOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    app_id: str
    workspace_id: str
    domain: str
    dns_verified: bool = False
    ssl_status: str = "pending"
    created_at: datetime


# ============ Monitoring & Alerts ============
class MonitoringResultOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    app_id: str
    timestamp: datetime
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    ok: bool


class AlertRuleIn(BaseModel):
    workspace_id: str
    app_id: Optional[str] = None
    type: Literal["app_down", "slow_response", "deployment_failure"]
    threshold: int = 0  # ms for slow_response, count for app_down
    cooldown_seconds: int = 600
    channels: List[Literal["in_app", "email"]] = Field(default_factory=lambda: ["in_app"])
    enabled: bool = True


class AlertRuleOut(AlertRuleIn):
    model_config = ConfigDict(extra="ignore")
    id: str
    last_triggered_at: Optional[datetime] = None
    created_at: datetime


# ============ Billing ============
class BillingProfileIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    address: str = Field(min_length=1, max_length=200)
    postal_code: str = Field(min_length=1, max_length=20)
    city: str = Field(min_length=1, max_length=80)
    country: str = Field(min_length=2, max_length=2)  # ISO-2
    email: EmailStr
    vat_id: Optional[str] = None
    is_business: bool = False


class BillingProfileOut(BillingProfileIn):
    model_config = ConfigDict(extra="ignore")
    workspace_id: str
    vat_id_valid: Optional[bool] = None
    vat_id_holder_name: Optional[str] = None
    vat_rate: Optional[float] = None
    vat_note: Optional[str] = None
    updated_at: datetime


class CheckoutIn(BaseModel):
    workspace_id: str
    plan: Literal["free", "hobby", "pro", "agency"]  # "hobby" kept as alias to "free"


class InvoiceOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    workspace_id: str
    invoice_number: str
    mollie_payment_id: Optional[str] = None
    subtotal: float
    vat_rate: float
    vat_amount: float
    vat_note: Optional[str] = None
    total: float
    currency: str = "EUR"
    status: str
    invoice_date: datetime
    due_date: Optional[datetime] = None
    pdf_url: Optional[str] = None


# ============ Notifications ============
class NotificationOut(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    workspace_id: str
    user_id: Optional[str] = None
    type: str
    title: str
    message: str
    severity: str = "info"
    read: bool = False
    link: Optional[str] = None
    created_at: datetime


# ============ Settings ============
class UserUpdateIn(BaseModel):
    name: Optional[str] = None


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)
