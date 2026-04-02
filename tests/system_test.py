#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
系统功能测试脚本
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from fastapi.testclient import TestClient
from backend.app import app

client = TestClient(app)

def test_cognitive_load_api():
    print("=== Test Cognitive Load API ===")
    response = client.post(
        "/api/cognitive-load/assess?save=true",
        headers={"X-User-Id": "test_user"},
        json={
            "user_id": "test_user",
            "session_id": "test_session",
            "task_id": "test_task",
            "source": "patient_education",
            "behavior_events": [],
            "nasa_tlx_answers": {
                "mental_demand": 4, "physical_demand": 3, "temporal_demand": 2,
                "performance": 5, "effort": 3, "frustration": 2
            }
        }
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Final Score: {result.get('final_score')}")
        print(f"Level: {result.get('level')}")
        print("PASS")
    else:
        print(f"Error: {response.text[:500]}")
    print()
    return response.status_code == 200


def test_cognitive_load_api_no_save():
    print("=== Test Cognitive Load API (no save) ===")
    response = client.post(
        "/api/cognitive-load/assess?save=false",
        headers={"X-User-Id": "test_user"},
        json={
            "user_id": "test_user",
            "task_id": "test_task",
            "source": "patient_education",
            "behavior_events": [{"event_type": "click", "ts": 1000, "params": {}}],
            "nasa_tlx_answers": {
                "mental_demand": 4, "physical_demand": 3, "temporal_demand": 2,
                "performance": 5, "effort": 3, "frustration": 2
            }
        }
    )
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Final Score: {result.get('final_score')}")
        print("PASS")
    else:
        print(f"Error: {response.text[:500]}")
    print()
    return response.status_code == 200


def test_history_api():
    print("=== Test History API ===")
    response = client.get("/api/history/list")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"History count: {len(result.get('data', {}).get('list', []))}")
        print("PASS")
    else:
        print(f"Error: {response.text[:200]}")
    print()
    return response.status_code == 200


def test_kb_api():
    print("=== Test KB API ===")
    response = client.get("/api/kb/bases")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("PASS")
    else:
        print(f"Error: {response.text[:200]}")
    print()
    return response.status_code == 200


def test_search_api():
    print("=== Test Search API ===")
    response = client.get("/api/search/entities?keyword=test")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("PASS")
    else:
        print(f"Error: {response.text[:200]}")
    print()
    return response.status_code == 200


def test_export_api():
    print("=== Test Export API ===")
    response = client.get("/api/cognitive-load/export?format=json&days=30")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print(f"Export count: {result.get('count', 0)}")
        print("PASS")
    else:
        print(f"Error: {response.text[:200]}")
    print()
    return response.status_code == 200


def test_kg_api():
    print("=== Test KG API ===")
    response = client.get("/api/kg/list")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("PASS")
    else:
        print(f"Error: {response.text[:200]}")
    print()
    return response.status_code == 200


def test_home_api():
    print("=== Test Home API ===")
    response = client.get("/api/home/overview")
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("PASS")
    else:
        print(f"Error: {response.text[:200]}")
    print()
    return response.status_code == 200


def main():
    print("=" * 50)
    print("System Function Tests")
    print("=" * 50)
    print()

    results = {
        "Cognitive Load API (no save)": test_cognitive_load_api_no_save(),
        "Cognitive Load API (with save)": test_cognitive_load_api(),
        "History API": test_history_api(),
        "KB API": test_kb_api(),
        "Search API": test_search_api(),
        "Export API": test_export_api(),
        "KG API": test_kg_api(),
        "Home API": test_home_api(),
    }

    print("=" * 50)
    print("Summary")
    print("=" * 50)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    for name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
    print("=" * 50)


if __name__ == "__main__":
    main()
