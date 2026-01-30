"""
Core Pub/Sub system implementation.
Handles topics, subscribers, message distribution, and backpressure management.
"""

import asyncio
import time
from collections import deque
from typing import Dict, Set, Optional
from datetime import datetime
import logging
from models import Message, ServerMessage, ErrorCode, ErrorDetail
from config import config

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)


class Subscriber:
    """
    Represents a single subscriber to a topic.
    Manages message queue and backpressure handling.
    """

    # Maximum number of messages in subscriber queue before backpressure kicks in
    MAX_QUEUE_SIZE = config.MAX_SUBSCRIBER_QUEUE_SIZE

    def __init__(self, client_id: str, websocket):
        """
        Initialize a subscriber.

        Args:
            client_id: Unique identifier for this subscriber
            websocket: WebSocket connection object
        """
        self.client_id = client_id
        self.websocket = websocket
        # Use asyncio.Queue for async-safe message queuing
        self.message_queue: asyncio.Queue = asyncio.Queue(maxsize=self.MAX_QUEUE_SIZE)
        self.active = True

    async def enqueue_message(self, message: Message, topic: str) -> bool:
        """
        Add a message to the subscriber's queue.
        Implements backpressure by dropping oldest message if queue is full.

        Args:
            message: The message to enqueue
            topic: Topic name for the message

        Returns:
            True if message was enqueued, False if dropped due to backpressure
        """
        try:
            # Non-blocking put - if queue is full, handle backpressure
            self.message_queue.put_nowait({
                'topic': topic,
                'message': message,
                'ts': datetime.utcnow().isoformat() + "Z"
            })
            return True
        except asyncio.QueueFull:
            # Backpressure policy: Drop oldest message and add new one
            logger.warning(f"Queue full for subscriber {self.client_id}. Dropping oldest message.")
            try:
                # Remove oldest message
                self.message_queue.get_nowait()
                # Add new message
                self.message_queue.put_nowait({
                    'topic': topic,
                    'message': message,
                    'ts': datetime.utcnow().isoformat() + "Z"
                })
                return True
            except Exception as e:
                logger.error(f"Error handling backpressure for {self.client_id}: {e}")
                return False

    async def get_message(self):
        """
        Retrieve next message from queue (blocking).

        Returns:
            Message dictionary with topic, message, and timestamp
        """
        return await self.message_queue.get()

    def deactivate(self):
        """Mark subscriber as inactive"""
        self.active = False


class Topic:
    """
    Represents a single topic in the Pub/Sub system.
    Manages subscribers and message history for replay functionality.
    """

    # Number of historical messages to retain for replay
    HISTORY_SIZE = config.TOPIC_HISTORY_SIZE

    def __init__(self, name: str):
        """
        Initialize a topic.

        Args:
            name: Topic name
        """
        self.name = name
        # Map of client_id -> Subscriber object
        self.subscribers: Dict[str, Subscriber] = {}
        # Circular buffer for message history (for last_n replay)
        self.message_history: deque = deque(maxlen=self.HISTORY_SIZE)
        # Total count of messages published to this topic
        self.message_count = 0
        # Lock for thread-safe operations
        self.lock = asyncio.Lock()

    async def add_subscriber(self, client_id: str, subscriber: Subscriber) -> None:
        """
        Add a subscriber to this topic.

        Args:
            client_id: Unique subscriber identifier
            subscriber: Subscriber object
        """
        async with self.lock:
            self.subscribers[client_id] = subscriber
            logger.info(f"Subscriber {client_id} added to topic '{self.name}'. Total: {len(self.subscribers)}")

    async def remove_subscriber(self, client_id: str) -> bool:
        """
        Remove a subscriber from this topic.

        Args:
            client_id: Subscriber to remove

        Returns:
            True if subscriber was found and removed, False otherwise
        """
        async with self.lock:
            if client_id in self.subscribers:
                subscriber = self.subscribers[client_id]
                subscriber.deactivate()
                del self.subscribers[client_id]
                logger.info(f"Subscriber {client_id} removed from topic '{self.name}'. Remaining: {len(self.subscribers)}")
                return True
            return False

    async def publish_message(self, message: Message) -> int:
        """
        Publish a message to all subscribers (fan-out).

        Args:
            message: Message to publish

        Returns:
            Number of subscribers who received the message
        """
        async with self.lock:
            # Add message to history for replay support
            self.message_history.append({
                'message': message,
                'ts': datetime.utcnow().isoformat() + "Z"
            })
            self.message_count += 1

            # Fan-out: Send to all active subscribers
            success_count = 0
            for subscriber in self.subscribers.values():
                if subscriber.active:
                    if await subscriber.enqueue_message(message, self.name):
                        success_count += 1

            logger.info(f"Published message to topic '{self.name}'. Delivered to {success_count}/{len(self.subscribers)} subscribers.")
            return success_count

    async def get_history(self, last_n: int) -> list:
        """
        Retrieve last N messages from history.

        Args:
            last_n: Number of messages to retrieve

        Returns:
            List of historical messages (oldest first)
        """
        async with self.lock:
            if last_n <= 0:
                return []
            # Get last N messages from deque
            history_list = list(self.message_history)
            return history_list[-last_n:] if last_n < len(history_list) else history_list

    def get_subscriber_count(self) -> int:
        """Get current number of active subscribers"""
        return len(self.subscribers)


class PubSubManager:
    """
    Central manager for the Pub/Sub system.
    Handles topic lifecycle, message routing, and system statistics.
    """

    def __init__(self):
        """Initialize the Pub/Sub manager"""
        # Map of topic_name -> Topic object
        self.topics: Dict[str, Topic] = {}
        # Lock for thread-safe topic operations
        self.lock = asyncio.Lock()
        # System start time for uptime calculation
        self.start_time = time.time()
        logger.info("PubSubManager initialized")

    async def create_topic(self, name: str) -> bool:
        """
        Create a new topic.

        Args:
            name: Topic name

        Returns:
            True if created, False if already exists
        """
        async with self.lock:
            if name in self.topics:
                logger.warning(f"Topic '{name}' already exists")
                return False
            self.topics[name] = Topic(name)
            logger.info(f"Topic '{name}' created. Total topics: {len(self.topics)}")
            return True

    async def delete_topic(self, name: str) -> bool:
        """
        Delete a topic and disconnect all subscribers.

        Args:
            name: Topic name

        Returns:
            True if deleted, False if not found
        """
        async with self.lock:
            if name not in self.topics:
                logger.warning(f"Topic '{name}' not found for deletion")
                return False

            topic = self.topics[name]

            # Notify all subscribers that topic is being deleted
            for subscriber in topic.subscribers.values():
                try:
                    info_msg = ServerMessage(
                        type="info",
                        topic=name,
                        msg="topic_deleted"
                    )
                    await subscriber.websocket.send_json(info_msg.model_dump(exclude_none=True))
                except Exception as e:
                    logger.error(f"Error notifying subscriber during topic deletion: {e}")

            # Remove topic
            del self.topics[name]
            logger.info(f"Topic '{name}' deleted. Remaining topics: {len(self.topics)}")
            return True

    async def subscribe(self, topic_name: str, client_id: str, websocket, last_n: int = 0) -> Optional[list]:
        """
        Subscribe a client to a topic.

        Args:
            topic_name: Topic to subscribe to
            client_id: Unique client identifier
            websocket: WebSocket connection
            last_n: Number of historical messages to replay

        Returns:
            List of historical messages if last_n > 0, None on error
        """
        async with self.lock:
            # Check if topic exists
            if topic_name not in self.topics:
                logger.warning(f"Subscribe failed: topic '{topic_name}' not found")
                return None

            topic = self.topics[topic_name]

        # Create subscriber
        subscriber = Subscriber(client_id, websocket)
        await topic.add_subscriber(client_id, subscriber)

        # Get historical messages if requested
        history = []
        if last_n > 0:
            history = await topic.get_history(last_n)

        return history

    async def unsubscribe(self, topic_name: str, client_id: str) -> bool:
        """
        Unsubscribe a client from a topic.

        Args:
            topic_name: Topic to unsubscribe from
            client_id: Client identifier

        Returns:
            True if unsubscribed, False if topic/subscriber not found
        """
        async with self.lock:
            if topic_name not in self.topics:
                logger.warning(f"Unsubscribe failed: topic '{topic_name}' not found")
                return False

            topic = self.topics[topic_name]

        return await topic.remove_subscriber(client_id)

    async def publish(self, topic_name: str, message: Message) -> Optional[int]:
        """
        Publish a message to a topic.

        Args:
            topic_name: Topic to publish to
            message: Message to publish

        Returns:
            Number of subscribers who received the message, None if topic not found
        """
        async with self.lock:
            if topic_name not in self.topics:
                logger.warning(f"Publish failed: topic '{topic_name}' not found")
                return None

            topic = self.topics[topic_name]

        return await topic.publish_message(message)

    async def get_all_topics(self) -> list:
        """
        Get information about all topics.

        Returns:
            List of topic info dictionaries
        """
        async with self.lock:
            return [
                {
                    'name': name,
                    'subscribers': topic.get_subscriber_count()
                }
                for name, topic in self.topics.items()
            ]

    async def get_stats(self) -> dict:
        """
        Get statistics for all topics.

        Returns:
            Dictionary mapping topic names to their statistics
        """
        async with self.lock:
            return {
                name: {
                    'messages': topic.message_count,
                    'subscribers': topic.get_subscriber_count()
                }
                for name, topic in self.topics.items()
            }

    def get_uptime(self) -> int:
        """
        Get system uptime in seconds.

        Returns:
            Uptime in seconds
        """
        return int(time.time() - self.start_time)

    def get_total_subscribers(self) -> int:
        """
        Get total number of subscribers across all topics.

        Returns:
            Total subscriber count
        """
        return sum(topic.get_subscriber_count() for topic in self.topics.values())

    def topic_exists(self, name: str) -> bool:
        """Check if a topic exists"""
        return name in self.topics
