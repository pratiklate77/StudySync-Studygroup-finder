import json
import logging
from typing import Any

logger = logging.getLogger("verification-service")


class ResilientKafkaProducer:
    """Resilient Kafka producer with fallback support."""
    
    def __init__(self, bootstrap_servers: str = "localhost:9092"):
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.is_connected = False
    
    async def start(self) -> bool:
        """Start Kafka producer."""
        try:
            from aiokafka import AIOKafkaProducer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers.split(","),
                compression_type="gzip",
                acks="all",
                enable_idempotence=True,
                linger_ms=10,
            )
            await self.producer.start()
            self.is_connected = True
            logger.info("Kafka producer started")
            return True
        except Exception as e:
            logger.warning(f"Failed to start Kafka producer: {e}. Continuing in fallback mode.")
            self.is_connected = False
            return False
    
    async def send(self, topic: str, value: Any, key: Any = None) -> bool:
        """Send message to Kafka."""
        if not self.is_connected or not self.producer:
            logger.warning(f"Kafka producer not available. Message not sent to {topic}")
            return False
        
        try:
            value_bytes = json.dumps(value).encode() if isinstance(value, dict) else value
            key_bytes = key.encode() if isinstance(key, str) else key
            await self.producer.send_and_wait(topic, value=value_bytes, key=key_bytes)
            return True
        except Exception as e:
            logger.error(f"Failed to send message to {topic}: {e}")
            return False
    
    async def stop(self) -> None:
        """Stop Kafka producer."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka producer stopped")
