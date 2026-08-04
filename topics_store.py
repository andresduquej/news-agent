"""
Topics Store — Sprint 1 (dashboard) del Agente de Contenido.

CRUD de temas/keywords dinámicos sobre un JSON local (topics.json).
Cada tema: nombre visible, query de búsqueda para Google News y flag activo.
La primera vez se siembra con los 5 temas históricos de news_fetcher.TOPICS.
"""

import json
from pathlib import Path

import news_fetcher

STORE = Path(__file__).resolve().parent / "topics.json"


def _seed() -> list:
    return [
        {"name": name, "query": query, "active": True}
        for name, query in news_fetcher.TOPICS.items()
    ]


def load() -> list:
    if not STORE.exists():
        save(_seed())
    return json.loads(STORE.read_text())


def save(topics: list) -> None:
    STORE.write_text(json.dumps(topics, ensure_ascii=False, indent=2))


def add(name: str, query: str = "") -> list:
    topics = load()
    if any(t["name"].lower() == name.lower() for t in topics):
        return topics
    topics.append({"name": name, "query": query or name, "active": True})
    save(topics)
    return topics


def remove(name: str) -> list:
    topics = [t for t in load() if t["name"].lower() != name.lower()]
    save(topics)
    return topics


def toggle(name: str, active: bool) -> list:
    topics = load()
    for t in topics:
        if t["name"].lower() == name.lower():
            t["active"] = active
    save(topics)
    return topics


def active_topics() -> list:
    return [t for t in load() if t["active"]]
