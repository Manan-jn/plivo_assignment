"""
Main FastAPI application for the Pub/Sub system.
Implements WebSocket endpoint for pub/sub operations and REST APIs for management.
"""

import asyncio
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, status
from fastapi.responses import JSONResponse

from models import (
    ClientMessage, ServerMessage, ErrorCode, ErrorDetail,
    CreateTopicRequest, CreateTopicResponse, DeleteTopicResponse,
    ListTopicsResponse, TopicInfo, HealthResponse, StatsResponse, TopicStats
)
from pubsub_manager import PubSubManager
from config import config, print_config

# Configure logging
logging.basicConfig(level=getattr(logging, config.LOG_LEVEL))
logger = logging.getLogger(__name__)

# Global PubSubManager instance
pubsub_manager = PubSubManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events for graceful operation.

    Implements graceful shutdown:
    1. Stop accepting new operations
    2. Notify all subscribers of shutdown
    3. Attempt to drain message queues (best-effort)
    4. Close WebSocket connections cleanly
    """
    # Startup
    logger.info("Starting Pub/Sub service...")
    logger.info(f"Server ready on {config.HOST}:{config.PORT}")

    yield  # Application runs here

    # Shutdown - Graceful cleanup
    logger.info("Shutting down Pub/Sub service gracefully...")

    try:
        # Step 1: Notify all subscribers of shutdown
        shutdown_tasks = []
        for topic in pubsub_manager.topics.values():
            for subscriber in topic.subscribers.values():
                try:
                    # Send shutdown notification
                    shutdown_msg = ServerMessage(
                        type="info",
                        msg="server_shutdown",
                        topic=topic.name
                    )
                    shutdown_tasks.append(
                        subscriber.websocket.send_json(shutdown_msg.model_dump(exclude_none=True))
                    )
                except Exception as e:
                    logger.error(f"Error notifying subscriber during shutdown: {e}")

        # Send all shutdown notifications concurrently
        if shutdown_tasks:
            await asyncio.gather(*shutdown_tasks, return_exceptions=True)
            logger.info(f"Notified {len(shutdown_tasks)} subscribers of shutdown")

        # Step 2: Execute comprehensive graceful shutdown
        await pubsub_manager.initiate_shutdown()

        # Step 3: Log final statistics
        logger.info(f"Final stats - Topics: {len(pubsub_manager.topics)}, "
                   f"Total subscribers: {pubsub_manager.get_total_subscribers()}")

        logger.info("Graceful shutdown completed")

    except Exception as e:
        logger.error(f"Error during graceful shutdown: {e}")


# Initialize FastAPI app
app = FastAPI(
    title="Pub/Sub System",
    description="In-memory Pub/Sub system with WebSocket and REST APIs",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# WebSocket Endpoint - /ws
# ============================================================================

async def send_error(websocket: WebSocket, error_code: ErrorCode, message: str, request_id: str = None):
    """
    Send an error message to the client.

    Args:
        websocket: WebSocket connection
        error_code: Error code enum
        message: Error description
        request_id: Optional request ID for correlation
    """
    error_msg = ServerMessage(
        type="error",
        request_id=request_id,
        error=ErrorDetail(code=error_code, message=message)
    )
    await websocket.send_json(error_msg.model_dump(exclude_none=True))


async def send_ack(websocket: WebSocket, topic: str = None, request_id: str = None):
    """
    Send an acknowledgment message to the client.

    Args:
        websocket: WebSocket connection
        topic: Topic name (optional)
        request_id: Request ID for correlation (optional)
    """
    ack_msg = ServerMessage(
        type="ack",
        request_id=request_id,
        topic=topic,
        status="ok"
    )
    await websocket.send_json(ack_msg.model_dump(exclude_none=True))


async def send_pong(websocket: WebSocket, request_id: str = None):
    """
    Send a pong response to client's ping.

    Args:
        websocket: WebSocket connection
        request_id: Request ID for correlation (optional)
    """
    pong_msg = ServerMessage(
        type="pong",
        request_id=request_id
    )
    await websocket.send_json(pong_msg.model_dump(exclude_none=True))


async def message_sender_task(websocket: WebSocket, client_id: str, topic_name: str):
    """
    Background task that sends queued messages to a subscriber.
    Runs until subscriber disconnects or unsubscribes.

    Args:
        websocket: WebSocket connection
        client_id: Subscriber's client ID
        topic_name: Topic the subscriber is subscribed to
    """
    # Get the topic and subscriber
    if not pubsub_manager.topic_exists(topic_name):
        return

    topic = pubsub_manager.topics[topic_name]
    if client_id not in topic.subscribers:
        return

    subscriber = topic.subscribers[client_id]

    try:
        while subscriber.active:
            # Wait for next message in queue
            msg_data = await subscriber.get_message()

            # Send event message to subscriber
            event_msg = ServerMessage(
                type="event",
                topic=msg_data['topic'],
                message=msg_data['message'],
                ts=msg_data['ts']
            )
            await websocket.send_json(event_msg.model_dump(exclude_none=True))

    except Exception as e:
        logger.error(f"Error in message sender task for {client_id}: {e}")
    finally:
        logger.info(f"Message sender task ended for subscriber {client_id}")


async def handle_subscribe(websocket: WebSocket, msg: ClientMessage):
    """
    Handle subscribe request from client.

    Args:
        websocket: WebSocket connection
        msg: Client message containing subscription details
    """
    # Check if system is shutting down
    if pubsub_manager.is_shutting_down():
        await send_error(websocket, ErrorCode.INTERNAL, "Server is shutting down, not accepting new subscriptions", msg.request_id)
        return
    
    # Validate required fields
    if not msg.topic:
        await send_error(websocket, ErrorCode.BAD_REQUEST, "topic is required", msg.request_id)
        return

    if not msg.client_id:
        await send_error(websocket, ErrorCode.BAD_REQUEST, "client_id is required", msg.request_id)
        return

    # Subscribe to topic
    history = await pubsub_manager.subscribe(
        topic_name=msg.topic,
        client_id=msg.client_id,
        websocket=websocket,
        last_n=msg.last_n or 0
    )

    if history is None:
        # Topic not found
        await send_error(websocket, ErrorCode.TOPIC_NOT_FOUND, f"Topic '{msg.topic}' does not exist", msg.request_id)
        return

    # Send acknowledgment
    await send_ack(websocket, topic=msg.topic, request_id=msg.request_id)

    # Send historical messages if requested
    if history:
        for hist_msg in history:
            event_msg = ServerMessage(
                type="event",
                topic=msg.topic,
                message=hist_msg['message'],
                ts=hist_msg['ts']
            )
            await websocket.send_json(event_msg.model_dump(exclude_none=True))

    # Start background task to send messages to this subscriber
    asyncio.create_task(message_sender_task(websocket, msg.client_id, msg.topic))


async def handle_unsubscribe(websocket: WebSocket, msg: ClientMessage):
    """
    Handle unsubscribe request from client.

    Args:
        websocket: WebSocket connection
        msg: Client message containing unsubscription details
    """
    # Validate required fields
    if not msg.topic:
        await send_error(websocket, ErrorCode.BAD_REQUEST, "topic is required", msg.request_id)
        return

    if not msg.client_id:
        await send_error(websocket, ErrorCode.BAD_REQUEST, "client_id is required", msg.request_id)
        return

    # Unsubscribe from topic
    success = await pubsub_manager.unsubscribe(msg.topic, msg.client_id)

    if not success:
        await send_error(websocket, ErrorCode.TOPIC_NOT_FOUND, f"Topic '{msg.topic}' not found or client not subscribed", msg.request_id)
        return

    # Send acknowledgment
    await send_ack(websocket, topic=msg.topic, request_id=msg.request_id)


async def handle_publish(websocket: WebSocket, msg: ClientMessage):
    """
    Handle publish request from client.

    Args:
        websocket: WebSocket connection
        msg: Client message containing message to publish
    """
    # Check if system is shutting down
    if pubsub_manager.is_shutting_down():
        await send_error(websocket, ErrorCode.INTERNAL, "Server is shutting down, not accepting new messages", msg.request_id)
        return
    
    # Validate required fields
    if not msg.topic:
        await send_error(websocket, ErrorCode.BAD_REQUEST, "topic is required", msg.request_id)
        return

    if not msg.message:
        await send_error(websocket, ErrorCode.BAD_REQUEST, "message is required", msg.request_id)
        return

    # Validate message ID is a valid UUID
    try:
        uuid.UUID(msg.message.id)
    except ValueError:
        await send_error(websocket, ErrorCode.BAD_REQUEST, "message.id must be a valid UUID", msg.request_id)
        return

    # Publish message to topic
    subscriber_count = await pubsub_manager.publish(msg.topic, msg.message)

    if subscriber_count is None:
        # Topic not found
        await send_error(websocket, ErrorCode.TOPIC_NOT_FOUND, f"Topic '{msg.topic}' does not exist", msg.request_id)
        return

    # Send acknowledgment
    await send_ack(websocket, topic=msg.topic, request_id=msg.request_id)


async def handle_ping(websocket: WebSocket, msg: ClientMessage):
    """
    Handle ping request from client.

    Args:
        websocket: WebSocket connection
        msg: Client message containing ping
    """
    await send_pong(websocket, request_id=msg.request_id)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for pub/sub operations.
    Handles: subscribe, unsubscribe, publish, ping messages.

    Args:
        websocket: WebSocket connection
    """
    # Check if system is shutting down before accepting connection
    if pubsub_manager.is_shutting_down():
        await websocket.close(code=1001, reason="Server is shutting down")
        logger.warning("Rejected WebSocket connection - server shutting down")
        return
    
    await websocket.accept()
    logger.info("WebSocket connection established")

    try:
        while True:
            # Check if shutdown initiated during connection
            if pubsub_manager.is_shutting_down():
                await send_error(websocket, ErrorCode.INTERNAL, "Server is shutting down")
                break
            
            # Receive message from client
            data = await websocket.receive_json()

            try:
                # Parse client message
                msg = ClientMessage(**data)

                # Route message to appropriate handler
                if msg.type == "subscribe":
                    await handle_subscribe(websocket, msg)
                elif msg.type == "unsubscribe":
                    await handle_unsubscribe(websocket, msg)
                elif msg.type == "publish":
                    await handle_publish(websocket, msg)
                elif msg.type == "ping":
                    await handle_ping(websocket, msg)
                else:
                    await send_error(websocket, ErrorCode.BAD_REQUEST, f"Unknown message type: {msg.type}")

            except Exception as e:
                logger.error(f"Error processing WebSocket message: {e}")
                await send_error(websocket, ErrorCode.BAD_REQUEST, f"Invalid message format: {str(e)}")

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        logger.info("WebSocket connection terminated")


# ============================================================================
# REST API Endpoints - Topic Management
# ============================================================================

@app.post("/topics", response_model=CreateTopicResponse, status_code=status.HTTP_201_CREATED)
async def create_topic(request: CreateTopicRequest):
    """
    Create a new topic.

    Args:
        request: Request body containing topic name

    Returns:
        CreateTopicResponse with status and topic name

    Raises:
        HTTPException: 409 if topic already exists
        HTTPException: 503 if server is shutting down
    """
    # Check if system is shutting down
    if pubsub_manager.is_shutting_down():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Server is shutting down, not accepting new operations"
        )
    
    success = await pubsub_manager.create_topic(request.name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Topic '{request.name}' already exists"
        )

    return CreateTopicResponse(topic=request.name)


@app.delete("/topics/{name}", response_model=DeleteTopicResponse)
async def delete_topic(name: str):
    """
    Delete a topic and disconnect all subscribers.

    Args:
        name: Topic name to delete

    Returns:
        DeleteTopicResponse with status and topic name

    Raises:
        HTTPException: 404 if topic not found
    """
    success = await pubsub_manager.delete_topic(name)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic '{name}' not found"
        )

    return DeleteTopicResponse(topic=name)


@app.get("/topics", response_model=ListTopicsResponse)
async def list_topics():
    """
    Get list of all topics with subscriber counts.

    Returns:
        ListTopicsResponse containing all topics
    """
    topics_data = await pubsub_manager.get_all_topics()
    topics = [TopicInfo(name=t['name'], subscribers=t['subscribers']) for t in topics_data]
    return ListTopicsResponse(topics=topics)


# ============================================================================
# REST API Endpoints - Observability
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Get system health information.

    Returns:
        HealthResponse with uptime, topic count, and subscriber count
    """
    return HealthResponse(
        uptime_sec=pubsub_manager.get_uptime(),
        topics=len(pubsub_manager.topics),
        subscribers=pubsub_manager.get_total_subscribers()
    )


@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get per-topic statistics.

    Returns:
        StatsResponse with message counts and subscriber counts per topic
    """
    stats_data = await pubsub_manager.get_stats()
    topics_stats = {
        name: TopicStats(messages=data['messages'], subscribers=data['subscribers'])
        for name, data in stats_data.items()
    }
    return StatsResponse(topics=topics_stats)


# ============================================================================
# Application Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    # Print configuration on startup
    print_config()

    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        log_level=config.LOG_LEVEL.lower(),
        access_log=True
    )
