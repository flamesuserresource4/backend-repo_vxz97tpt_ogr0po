import os
from typing import List, Optional
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import date, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class KPI(BaseModel):
    label: str
    value: float
    delta: Optional[float] = None
    help: Optional[str] = None


class VelocityPoint(BaseModel):
    key: str
    start: date
    end: date
    committed: float
    completed: float


class CommitmentPoint(BaseModel):
    sprint: str
    committed: float
    completed: float
    rollover: float
    percent: float


class RolloverPoint(BaseModel):
    sprint: str
    percent: float
    committed: float
    rolled: float


class ScopeSummary(BaseModel):
    avg_added: float
    avg_removed: float
    avg_net_percent: float


class SprintRow(BaseModel):
    sprint: str
    start: date
    end: date
    committed: float
    completed: float
    completion_percent: float
    rollover_points: float
    rollover_percent: float
    dor_compliance_percent: float
    bugs_created: int
    items_reopened: int


class TeamDashboardResponse(BaseModel):
    team_name: str
    kpis: List[KPI]
    velocity: List[VelocityPoint]
    commitment_vs_completion: List[CommitmentPoint]
    rollover_trend: List[RolloverPoint]
    scope_change: ScopeSummary
    sprint_rows: List[SprintRow]


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        from database import db

        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


@app.get("/api/team-dashboard", response_model=TeamDashboardResponse)
def team_dashboard(
    team_id: str = Query("team-1"),
    team_name: str = Query("Alpha Team"),
    grouping: str = Query("By sprint", pattern="^(By sprint|By week|By month)$"),
    include_done_only: bool = Query(False),
    item_types: List[str] = Query(["Stories", "Bugs", "Tasks", "Epics"]) 
):
    """
    Demo analytics endpoint. In a real implementation we would:
    - Query the connected work management system (Jira/Azure DevOps)
    - Or aggregate from our MongoDB where work items are synced
    For now, we synthesize realistic data deterministically from the inputs.
    """
    # deterministic seed from team_id
    base_points = 30 if include_done_only else 35
    sprint_count = 8

    velocity: List[VelocityPoint] = []
    commit_vs: List[CommitmentPoint] = []
    rollover_points: List[RolloverPoint] = []
    rows: List[SprintRow] = []

    today = date.today()
    # Assume sprints are 2 weeks, retros on Mondays
    for i in range(sprint_count):
        idx = sprint_count - i
        sprint_name = f"Sprint {idx}"
        start = today - timedelta(weeks=(sprint_count - i) * 2)
        end = start + timedelta(days=13)

        committed = base_points + (i % 3) * 5 + 5
        completed = max(0.0, committed - (i % 4) * 4 + ((i % 2) * 2))
        completed = round(min(committed + 3, completed), 1)
        rollover = max(0.0, round(committed - completed, 1))
        percent = round(100.0 * (completed / committed) if committed else 0, 1)
        roll_percent = round(100.0 * (rollover / committed) if committed else 0, 1)
        dor = round(80 + (i % 5) * 3 - (i % 2), 1)
        bugs_created = 5 + (i % 4) * 2
        reopened = (i % 3)

        velocity.append(VelocityPoint(key=sprint_name, start=start, end=end, committed=committed, completed=completed))
        commit_vs.append(CommitmentPoint(sprint=sprint_name, committed=committed, completed=completed, rollover=rollover, percent=percent))
        rollover_points.append(RolloverPoint(sprint=sprint_name, percent=roll_percent, committed=committed, rolled=rollover))
        rows.append(
            SprintRow(
                sprint=sprint_name,
                start=start,
                end=end,
                committed=committed,
                completed=completed,
                completion_percent=percent,
                rollover_points=rollover,
                rollover_percent=roll_percent,
                dor_compliance_percent=dor,
                bugs_created=bugs_created,
                items_reopened=reopened,
            )
        )

    # KPIs (averages across range)
    avg_velocity = round(sum(v.completed for v in velocity) / len(velocity), 1)
    avg_throughput = round((sum(1 for _ in velocity) * 10) / len(velocity), 1)  # demo placeholder
    commitment_completion = round(sum(c.completed for c in commit_vs) / sum(c.committed for c in commit_vs) * 100, 1)
    rollover_rate = round(sum(c.rollover for c in commit_vs) / sum(c.committed for c in commit_vs) * 100, 1)
    dor_compliance = round(sum(r.dor_compliance_percent for r in rows) / len(rows), 1)
    bug_ratio = round((sum(r.bugs_created for r in rows) / max(1, len(rows) * 12)), 2)

    kpis = [
        KPI(label="Velocity", value=avg_velocity, delta=1.2, help="Average story points completed per sprint in the selected range."),
        KPI(label="Throughput", value=avg_throughput, delta=-0.5, help="Number of items completed per sprint in the selected range."),
        KPI(label="Commitment completion %", value=commitment_completion, delta=2.1, help="Completed points divided by points committed at sprint start."),
        KPI(label="Rollover rate %", value=rollover_rate, delta=-1.4, help="Rolled-over points divided by committed points."),
        KPI(label="DoR compliance %", value=dor_compliance, delta=0.8, help="Percentage of items that met Definition of Ready before sprint start."),
        KPI(label="Bug ratio", value=bug_ratio, delta=-0.1, help="Number of bugs divided by number of stories completed."),
    ]

    scope = ScopeSummary(
        avg_added=round(3.2, 1),
        avg_removed=round(1.4, 1),
        avg_net_percent=round(6.5, 1),
    )

    # Sort by sprint name numeric part descending (latest first)
    velocity_sorted = list(reversed(velocity))
    commit_sorted = list(reversed(commit_vs))
    rollover_sorted = list(reversed(rollover_points))
    rows_sorted = list(reversed(rows))

    return TeamDashboardResponse(
        team_name=team_name,
        kpis=kpis,
        velocity=velocity_sorted,
        commitment_vs_completion=commit_sorted,
        rollover_trend=rollover_sorted,
        scope_change=scope,
        sprint_rows=rows_sorted,
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
