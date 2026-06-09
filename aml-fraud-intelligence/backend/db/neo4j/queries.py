"""
Cypher query library — all Neo4j queries defined as constants.
Never inline Cypher strings in application code.
"""

# ─── Schema setup ─────────────────────────────────────────────────────────────

CREATE_CONSTRAINTS = """
CREATE CONSTRAINT account_id_unique IF NOT EXISTS FOR (a:Account) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT customer_id_unique IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT device_id_unique IF NOT EXISTS FOR (d:Device) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT merchant_id_unique IF NOT EXISTS FOR (m:Merchant) REQUIRE m.id IS UNIQUE;
"""

CREATE_INDEXES = """
CREATE INDEX account_risk_score IF NOT EXISTS FOR (a:Account) ON (a.risk_score);
CREATE INDEX tx_timestamp IF NOT EXISTS FOR ()-[r:TRANSFERRED_TO]-() ON (r.timestamp);
"""

# ─── Node + Relationship upserts ──────────────────────────────────────────────

UPSERT_ACCOUNT = """
MERGE (a:Account {id: $id})
SET a.type       = $type,
    a.bank_code  = $bank_code,
    a.country    = $country,
    a.is_dormant = $is_dormant,
    a.risk_score = coalesce($risk_score, a.risk_score, 0.0)
RETURN a
"""

UPSERT_CUSTOMER = """
MERGE (c:Customer {id: $customer_id})
SET c.risk_tier = $risk_tier,
    c.country   = $country
WITH c
MATCH (a:Account {id: $account_id})
MERGE (c)-[:OWNS]->(a)
RETURN c, a
"""

UPSERT_DEVICE = """
MERGE (d:Device {id: $device_id})
SET d.ip_hash = $ip_hash
WITH d
MATCH (a:Account {id: $account_id})
MERGE (a)-[:USED_DEVICE {timestamp: $timestamp}]->(d)
"""

CREATE_TRANSFER = """
MATCH (src:Account {id: $sender_id}), (dst:Account {id: $receiver_id})
MERGE (src)-[r:TRANSFERRED_TO {tx_id: $tx_id}]->(dst)
SET r.amount    = $amount,
    r.timestamp = $timestamp,
    r.channel   = $channel
RETURN r
"""

# ─── Graph analysis queries ───────────────────────────────────────────────────

CYCLE_DETECTION = """
MATCH path = (a:Account)-[:TRANSFERRED_TO*3..6]->(a)
WHERE ALL(r IN relationships(path)
      WHERE r.timestamp > datetime() - duration('P3D'))
WITH a, path,
     [r IN relationships(path) | r.amount]    AS amounts,
     [r IN relationships(path) | r.timestamp] AS timestamps
RETURN a.id              AS account_id,
       length(path)      AS hops,
       amounts,
       timestamps,
       reduce(s=0.0, x IN amounts | s + x) AS total_amount
ORDER BY hops ASC
LIMIT 100
"""

LAYERING_DETECTION = """
MATCH path = (src:Account)-[:TRANSFERRED_TO*4..8]->(dst:Account)
WHERE src <> dst
  AND ALL(r IN relationships(path) WHERE r.timestamp > datetime() - duration('P7D'))
  AND src.bank_code <> dst.bank_code
WITH src, dst, path,
     [r IN relationships(path) | r.amount] AS amounts
RETURN src.id                                               AS source_account,
       dst.id                                               AS dest_account,
       length(path)                                         AS depth,
       reduce(total=0.0, r IN relationships(path) | total + r.amount) AS total_moved,
       amounts
ORDER BY depth DESC
LIMIT 50
"""

MULE_DETECTION = """
MATCH (a:Account)
WITH a,
     size((a)<-[:TRANSFERRED_TO]-())  AS in_degree,
     size((a)-[:TRANSFERRED_TO]->())   AS out_degree
WHERE in_degree > 8 AND out_degree BETWEEN 1 AND 3
RETURN a.id                                      AS account_id,
       in_degree,
       out_degree,
       toFloat(out_degree) / in_degree           AS concentration_ratio,
       a.bank_code                               AS bank_code,
       a.country                                 AS country
ORDER BY in_degree DESC
LIMIT 100
"""

PAGERANK_STREAM = """
CALL gds.pageRank.stream('transactionGraph', {
    dampingFactor: 0.85,
    maxIterations: 20
})
YIELD nodeId, score
RETURN gds.util.asNode(nodeId).id AS account_id, score
ORDER BY score DESC
LIMIT 200
"""

GET_NEIGHBORS_2HOP = """
MATCH (src:Account {id: $account_id})-[:TRANSFERRED_TO*1..2]-(nbr:Account)
WHERE nbr <> src
WITH DISTINCT nbr,
     [(nbr)<-[:TRANSFERRED_TO]-() | 1] AS in_edges,
     [(nbr)-[:TRANSFERRED_TO]->() | 1] AS out_edges
RETURN nbr.id         AS account_id,
       nbr.bank_code  AS bank_code,
       nbr.country    AS country,
       nbr.risk_score AS risk_score,
       nbr.is_dormant AS is_dormant,
       size(in_edges)  AS in_degree,
       size(out_edges) AS out_degree
ORDER BY nbr.risk_score DESC
LIMIT 50
"""

GET_ACCOUNT_GRAPH_METRICS = """
MATCH (a:Account {id: $account_id})
WITH a,
     size((a)<-[:TRANSFERRED_TO]-()) AS in_degree,
     size((a)-[:TRANSFERRED_TO]->()) AS out_degree
OPTIONAL MATCH (a)-[:TRANSFERRED_TO*3..6]->(a)
WITH a, in_degree, out_degree,
     count(*) AS cycle_count
RETURN a.id       AS account_id,
       in_degree,
       out_degree,
       cycle_count,
       a.risk_score AS stored_risk_score
"""

GDS_GRAPH_PROJECT = """
CALL gds.graph.project(
    'transactionGraph',
    'Account',
    {TRANSFERRED_TO: {properties: ['amount']}}
)
"""

UPDATE_ACCOUNT_RISK = """
MATCH (a:Account {id: $account_id})
SET a.risk_score = $risk_score
RETURN a.id, a.risk_score
"""
