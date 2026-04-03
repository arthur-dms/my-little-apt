"""
Redis Pub/Sub message broker.
Handles publishing and subscribing to Redis channels for bot ↔ server
communication.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

import redis.asyncio as aioredis

from config import (
    REDIS_CHANNEL_COMMANDS,
    REDIS_CHANNEL_RESPONSES,
    REDIS_DB,
    REDIS_HOST,
    REDIS_PORT,
)

logger = logging.getLogger("c2-server.mq")


class MessageBroker:
    """Async Redis Pub/Sub wrapper for command/response messaging."""

    def __init__(
        self,
        host: str = REDIS_HOST,
        port: int = REDIS_PORT,
        db: int = REDIS_DB,
        commands_channel: str = REDIS_CHANNEL_COMMANDS,
        responses_channel: str = REDIS_CHANNEL_RESPONSES,
        redis_client: aioredis.Redis | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.db = db
        self.commands_channel = commands_channel
        self.responses_channel = responses_channel
        self._redis: aioredis.Redis | None = redis_client
        self._pubsub: aioredis.client.PubSub | None = None
        self._listening = False

    async def connect(self) -> None:
        """Establish the Redis connection."""
        if self._redis is None:
            self._redis = aioredis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True,
            )
        logger.info(
            "Connected to Redis at %s:%d (db=%d)",
            self.host,
            self.port,
            self.db,
        )

    async def disconnect(self) -> None:
        """Close the Redis connection and any active subscriptions."""
        self._listening = False
        if self._pubsub:
            await self._pubsub.unsubscribe()
            await self._pubsub.close()
            self._pubsub = None
        if self._redis:
            await self._redis.close()
            self._redis = None
        logger.info("Disconnected from Redis")

    async def publish(self, channel: str, message: dict[str, Any]) -> int:
        """
        Publish a JSON-serialised message to a Redis channel.
        Returns the number of subscribers that received the message.
        """
        if not self._redis:
            raise RuntimeError("MessageBroker is not connected. Call connect() first.")

        payload = json.dumps(message, default=str)
        subscribers = await self._redis.publish(channel, payload)
        logger.debug(
            "Published to %s (%d subscriber(s)): %s",
            channel,
            subscribers,
            payload[:200],
        )
        return subscribers

    async def publish_response(self, message: dict[str, Any]) -> int:
        """Publish a message to the responses channel."""
        return await self.publish(self.responses_channel, message)

    async def publish_command(self, message: dict[str, Any]) -> int:
        """Publish a message to the commands channel."""
        return await self.publish(self.commands_channel, message)

    async def subscribe_commands(
        self,
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Subscribe to the commands channel and call *handler* for each
        incoming message. Blocks until stop_listening() is called.
        """
        await self._subscribe(self.commands_channel, handler)

    async def subscribe_responses(
        self,
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """
        Subscribe to the responses channel and call *handler* for each
        incoming message. Blocks until stop_listening() is called.
        """
        await self._subscribe(self.responses_channel, handler)

    async def _subscribe(
        self,
        channel: str,
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Internal: subscribe to a channel and dispatch messages."""
        if not self._redis:
            raise RuntimeError("MessageBroker is not connected. Call connect() first.")

        self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(channel)
        logger.info("Subscribed to channel: %s", channel)

        self._listening = True
        while self._listening:
            try:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if message and message["type"] == "message":
                    data = json.loads(message["data"])
                    await handler(data)
            except asyncio.CancelledError:
                logger.info("Listener cancelled for channel: %s", channel)
                break
            except json.JSONDecodeError as exc:
                logger.error("Invalid JSON on %s: %s", channel, exc)
            except Exception as exc:
                logger.error("Error processing message on %s: %s", channel, exc)
                await asyncio.sleep(1)

    def stop_listening(self) -> None:
        """Signal the subscription loop to stop."""
        self._listening = False
