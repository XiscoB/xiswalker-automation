import os
import yaml
import pytest
from xiswalker.models import parse_schedules_yaml, ScheduleTask

def test_parse_schedules_yaml_valid(tmp_path):
    yaml_content = {
        "schedules": [
            {
                "name": "evening_farm",
                "composite": "evening_farm_composite",
                "time": "19:55",
                "days": ["mon", "tue", "wed", "thu", "fri"],
                "safe_mode": False
            },
            {
                "name": "night_boss_check",
                "composite": "boss_look",
                "time": "20:25",
                "days": ["tue", "thu"],
                "repeat": 3
            }
        ]
    }
    file_path = tmp_path / "schedules.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(yaml_content, f)

    tasks = parse_schedules_yaml(str(file_path))

    assert len(tasks) == 2
    
    assert tasks[0].name == "evening_farm"
    assert tasks[0].composite == "evening_farm_composite"
    assert tasks[0].time == "19:55"
    assert list(tasks[0].days) == ["mon", "tue", "wed", "thu", "fri"]
    assert tasks[0].safe_mode is False
    assert tasks[0].repeat == 1

    assert tasks[1].name == "night_boss_check"
    assert tasks[1].composite == "boss_look"
    assert tasks[1].time == "20:25"
    assert list(tasks[1].days) == ["tue", "thu"]
    assert tasks[1].safe_mode is False
    assert tasks[1].repeat == 3

def test_parse_schedules_yaml_empty(tmp_path):
    file_path = tmp_path / "empty.yaml"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("")
        
    tasks = parse_schedules_yaml(str(file_path))
    assert tasks == []
    
def test_parse_schedules_yaml_missing():
    tasks = parse_schedules_yaml("nonexistent_file_path_12345.yaml")
    assert tasks == []
