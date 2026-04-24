import pytest
from pydantic import ValidationError

from app.ingestion.kg_extract import RELATION_ALLOWLIST, _slugify, parse_extraction


def test_parse_extraction_clamps_unknown_relation() -> None:
    raw = """{
      "entities": [
        {"id": "acme", "name": "Acme", "kind": "organization", "aliases": [], "date": null,
         "theme": null, "description": ""},
        {"id": "paris", "name": "Paris", "kind": "location", "aliases": [], "date": null,
         "theme": null, "description": ""}
      ],
      "relations": [
        {"src": "Acme", "dst": "Paris", "type": "HEADQUARTERED_IN", "evidence": "..."}
      ]
    }"""
    out = parse_extraction(raw)
    assert len(out.entities) == 2
    # unknown type was clamped to RELATED_TO (guaranteed in allowlist).
    assert len(out.relations) == 1
    assert out.relations[0].type in RELATION_ALLOWLIST
    # ids slugified
    assert out.relations[0].src == "acme"
    assert out.relations[0].dst == "paris"


def test_parse_rejects_extra_fields() -> None:
    raw = """{
      "entities": [{"id": "x", "name": "x", "kind": "person", "extra": true}],
      "relations": []
    }"""
    with pytest.raises(ValidationError):
        parse_extraction(raw)


def test_parse_with_fence() -> None:
    fenced = "```json\n" + """{"entities":[],"relations":[]}""" + "\n```"
    out = parse_extraction(fenced)
    assert out.entities == []
    assert out.relations == []


def test_slugify() -> None:
    assert _slugify("Acme Corp") == "acme-corp"
    assert _slugify("---") == "entity"
    assert _slugify("MixedCASE_123") == "mixedcase-123"


def test_kg_endpoints_return_503_when_neo4j_absent(client):
    # A workspace must exist; outsider is blocked at 403 before reaching the KG service.
    client.post(
        "/api/auth/register",
        json={"email": "owner@example.com", "password": "s3cretpass!", "display_name": "o"},
    )
    tok = client.post(
        "/api/auth/login", json={"email": "owner@example.com", "password": "s3cretpass!"}
    ).json()["access_token"]
    ws_id = client.post(
        "/api/workspaces",
        headers={"Authorization": f"Bearer {tok}"},
        json={"name": "Acme", "slug": "acme", "description": ""},
    ).json()["id"]
    r = client.get(
        "/api/kg/timeline",
        headers={"Authorization": f"Bearer {tok}"},
        params={"workspace_id": ws_id},
    )
    assert r.status_code == 503
    assert "KG unavailable" in r.json()["detail"]
