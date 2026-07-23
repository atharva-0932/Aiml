"""
ml_scorer consumer — Redis velocity + XGBoost + GraphRisk + composite score.

Run: PYTHONPATH=backend python3 -m kafka.consumers.ml_scorer
"""
from __future__ import annotations

import asyncio

from confluent_kafka import Consumer, KafkaError, KafkaException

from core.config import settings
from db.redis.cache import (
    cache_graph_risk,
    cache_risk_score,
    get_cached_graph_risk,
    get_velocity_features,
    update_velocity,
)
from db.redis.client import close_redis
from db.supabase.client import (
    close_pool,
    insert_alert,
    insert_shap_explanations,
    upsert_transaction,
)
from graph.scorer import GraphRiskScorer
from kafka.serde import deserialize_transaction
from kafka.topics import TX_RAW, ensure_topics
from ml.features import extract_features
from ml.scorer import CompositeRiskScorer, XGBoostScorer


def _build_consumer() -> Consumer:
    return Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": "ml_scorer",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })


async def _graph_score_cached(graph_scorer: GraphRiskScorer, account_id: str) -> dict:
    cached = await get_cached_graph_risk(account_id)
    if cached is not None:
        return cached
    result = await graph_scorer.score(account_id)
    await cache_graph_risk(account_id, result)
    return result


async def process_message(
    tx: dict,
    xgb_scorer: XGBoostScorer,
    graph_scorer: GraphRiskScorer,
    composite_scorer: CompositeRiskScorer,
) -> dict:
    sender = tx["sender_account"]
    receiver = tx["receiver_account"]
    amount = float(tx["amount"])

    velocity = await get_velocity_features(sender)
    features = extract_features(tx, velocity=velocity, amount_mean=xgb_scorer.amount_mean)
    xgb_score = xgb_scorer.score(features)
    graph = await _graph_score_cached(graph_scorer, sender)
    combined = composite_scorer.composite(xgb_score, float(graph.get("graph_risk", 0.0)))

    shap_top = xgb_scorer.shap_top_features(features, top_k=5)

    await cache_risk_score(tx["transaction_id"], combined["composite_score"])
    await update_velocity(sender, receiver, amount)
    await upsert_transaction(tx, combined["composite_score"])
    await insert_shap_explanations(tx["transaction_id"], shap_top)

    if combined["composite_score"] > 70:
        await insert_alert(
            tx["transaction_id"],
            combined["composite_score"],
            tx.get("pattern_label"),
        )

    return {
        **combined,
        "flags": graph.get("flags", []),
        "shap_top": shap_top,
    }


async def run() -> None:
    ensure_topics()
    xgb_scorer = XGBoostScorer()
    graph_scorer = GraphRiskScorer()
    composite_scorer = CompositeRiskScorer()

    consumer = _build_consumer()
    consumer.subscribe([TX_RAW])
    print(f"ml_scorer listening on {TX_RAW} (group=ml_scorer, XGBoost+Graph composite)")
    processed = 0

    try:
        while True:
            msg = consumer.poll(timeout=0.1)
            if msg is None:
                await asyncio.sleep(0)
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                raise KafkaException(msg.error())

            try:
                tx = deserialize_transaction(msg.value())
                result = await process_message(tx, xgb_scorer, graph_scorer, composite_scorer)
                consumer.commit(asynchronous=False)
                processed += 1
                label = tx.get("pattern_label")
                if processed % 100 == 0 or processed <= 5 or label or result["composite_score"] > 70:
                    print(
                        f"[{processed}] tx={tx['transaction_id'][:8]}… "
                        f"score={result['composite_score']:.1f} tier={result['tier']} "
                        f"label={label} flags={result['flags']}"
                    )
            except Exception as exc:
                print(f"ERROR processing message: {exc}")
    finally:
        consumer.close()
        await close_redis()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(run())
