import pytest

from app.models import ResearchResult, ScanRun, VerificationQueue
from app.schemas import ResearchSettings
from app.services.demo_data import demo_candidates
from app.services.pipeline import ResearchPipeline


@pytest.mark.asyncio
async def test_demo_pipeline_delivers_pass_fail_verify_and_detail_data(db):
    scan = ScanRun(mode="demo", status="QUEUED", query="demo")
    db.add(scan)
    db.commit()
    db.refresh(scan)

    await ResearchPipeline(db, ResearchSettings()).run(scan, demo_candidates())

    results = db.query(ResearchResult).all()
    statuses = {row.status for row in results}
    assert statuses == {"PASS", "FAIL", "VERIFY"}
    assert scan.status == "COMPLETED"
    assert scan.progress == 100
    assert scan.pass_count == 1
    assert scan.fail_count == 1
    assert scan.verify_count == 1
    passing = next(row for row in results if row.status == "PASS")
    assert passing.profit is not None and passing.profit >= 20
    assert passing.cheapest_offer is not None
    assert passing.demand_sellers[0]["signal"] == "Allegro API sellingMode.popularity"
    assert db.query(VerificationQueue).count() >= 1
