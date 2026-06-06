#!/bin/bash
set -e

ZK_HOST="${KAFKA_ZOOKEEPER_CONNECT:-zookeeper:2181}"
BROKER_ID="${KAFKA_BROKER_ID:-1}"
LOG_DIR="${KAFKA_LOG_DIRS:-/var/lib/kafka/data}"
META_FILE="$LOG_DIR/meta.properties"

echo "==> Waiting for Zookeeper at $ZK_HOST..."
until zookeeper-shell "$ZK_HOST" ls / > /dev/null 2>&1; do
  echo "==> Zookeeper not ready, retrying in 2s..."
  sleep 2
done
echo "==> Zookeeper is ready"

# Delete stale broker ephemeral node
echo "==> Removing stale broker registration /brokers/ids/$BROKER_ID..."
zookeeper-shell "$ZK_HOST" rmr /brokers/ids/"$BROKER_ID" 2>/dev/null || true

# Fix cluster ID mismatch
if [ -f "$META_FILE" ]; then
  LOCAL_CLUSTER_ID=$(grep "^cluster.id=" "$META_FILE" | cut -d= -f2)
  if [ -n "$LOCAL_CLUSTER_ID" ]; then
    ZK_CLUSTER_JSON=$(zookeeper-shell "$ZK_HOST" get /cluster/id 2>/dev/null || true)
    ZK_CLUSTER_ID=$(echo "$ZK_CLUSTER_JSON" | grep -o '"id":"[^"]*"' | cut -d'"' -f4 || true)
    if [ -n "$ZK_CLUSTER_ID" ] && [ "$ZK_CLUSTER_ID" != "$LOCAL_CLUSTER_ID" ]; then
      echo "==> Cluster ID mismatch — wiping meta.properties and Zookeeper cluster ID..."
      zookeeper-shell "$ZK_HOST" rmr /cluster/id 2>/dev/null || true
      rm -f "$META_FILE"
    fi
  fi
fi

echo "==> Starting Kafka..."
exec /etc/confluent/docker/run
