import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]

def test_site_data_summary_schema():
    summary_path = ROOT / "site_data_summary.json"
    assert summary_path.exists(), "site_data_summary.json does not exist"
    
    with open(summary_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Check top-level keys
    required_keys = {
        "schema_version",
        "generated",
        "build",
        "summary",
        "stats",
        "geography_stats",
        "gender_stats",
        "age_stats",
        "generation_stats",
        "institutions_stats",
        "word_cloud",
        "scholars"
    }
    for key in required_keys:
        assert key in data, f"Key '{key}' missing from site_data_summary.json"
        
    # Validate scholars entries (should not contain 'talks')
    assert isinstance(data["scholars"], list), "'scholars' must be a list"
    assert len(data["scholars"]) > 0, "'scholars' list is empty"
    for scholar in data["scholars"]:
        assert "id" in scholar, "Scholar missing 'id'"
        assert "name" in scholar, "Scholar missing 'name'"
        assert "talks" not in scholar, "Scholar summary should have 'talks' popped out for performance"

def test_site_data_timeline_chunks():
    timeline_path = ROOT / "site_data_timeline.json"
    assert timeline_path.exists(), "site_data_timeline.json does not exist"
    
    with open(timeline_path, "r", encoding="utf-8") as f:
        timeline_data = json.load(f)
        
    assert isinstance(timeline_data, dict), "Timeline data must be a dictionary"
    assert len(timeline_data) > 0, "Timeline has no years"
    
    # Check that individual year files exist and match their chunks in site_data_timeline.json
    for year, year_data in timeline_data.items():
        year_file = ROOT / f"site_data_timeline_{year}.json"
        assert year_file.exists(), f"site_data_timeline_{year}.json does not exist"
        
        with open(year_file, "r", encoding="utf-8") as f:
            chunk_data = json.load(f)
            
        assert chunk_data == year_data, f"Chunk data in site_data_timeline_{year}.json does not match main timeline"
