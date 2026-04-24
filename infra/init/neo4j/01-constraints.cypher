// Neo4j constraints & indexes — executed manually or by the backend during P4 init.
// Mount path: /var/lib/neo4j/import (read-only inside the container).
//
// Planned indexes (add when Entity/Event nodes are introduced):
//
//   CREATE INDEX entity_workspace_name IF NOT EXISTS
//       FOR (e:Entity) ON (e.workspace_id, e.name);
//
//   CREATE INDEX event_workspace_date IF NOT EXISTS
//       FOR (ev:Event) ON (ev.workspace_id, ev.date);
//
//   CREATE INDEX event_workspace_theme IF NOT EXISTS
//       FOR (ev:Event) ON (ev.workspace_id, ev.theme);
//
//   CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
//       FOR (e:Entity) REQUIRE e.id IS UNIQUE;
//
// Until P4 we only ensure the database starts cleanly.
