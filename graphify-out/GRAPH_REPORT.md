# Graph Report - The-Warden  (2026-08-19)

## Corpus Check
- Corpus is ~225 words - fits in a single context window. You may not need a graph.

## Summary
- 30 nodes · 32 edges · 9 communities (7 shown, 2 thin omitted)
- Extraction: 97% EXTRACTED · 3% INFERRED · 0% AMBIGUOUS · INFERRED: 1 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Bot Entrypoint & Wiring
- Ping Setup & Service
- Ping Handler & Protocol
- Ping Command Interface
- Ping Handler Bot Dependency

## God Nodes (most connected - your core abstractions)
1. `PingHandlers` - 6 edges
2. `PingService` - 5 edges
3. `Warden` - 4 edges
4. `setup()` - 4 edges
5. `PingService` - 4 edges
6. `feature_modules()` - 3 edges
7. `Every feature package under warden/features/. Adding one = adding a folder.` - 1 edges
8. `Ping feature. Wiring only — handlers and services live in their own folders.` - 1 edges

## Surprising Connections (you probably didn't know these)
- `setup()` --calls--> `PingHandlers`  [EXTRACTED]
  warden/features/ping/__init__.py → warden/features/ping/handlers/ping_handler.py
- `PingHandlers` --uses--> `PingService`  [INFERRED]
  warden/features/ping/handlers/ping_handler.py → warden/features/ping/services/protocol.py
- `setup()` --calls--> `PingService`  [EXTRACTED]
  warden/features/ping/__init__.py → warden/features/ping/services/ping_service.py

## Import Cycles
- None detected.

## Communities (9 total, 2 thin omitted)

### Community 0 - "Bot Entrypoint & Wiring"
Cohesion: 0.38
Nodes (3): feature_modules(), Every feature package under warden/features/. Adding one = adding a folder., Warden

### Community 1 - "Ping Setup & Service"
Cohesion: 0.38
Nodes (4): Bot, Ping feature. Wiring only — handlers and services live in their own folders., setup(), PingService

### Community 2 - "Ping Handler & Protocol"
Cohesion: 0.47
Nodes (3): Protocol, PingHandlers, PingService

## Knowledge Gaps
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PingHandlers` connect `Ping Handler & Protocol` to `Ping Setup & Service`, `Ping Command Interface`, `Ping Handler Bot Dependency`?**
  _High betweenness centrality (0.241) - this node is a cross-community bridge._
- **Why does `setup()` connect `Ping Setup & Service` to `Ping Handler & Protocol`?**
  _High betweenness centrality (0.064) - this node is a cross-community bridge._