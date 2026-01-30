# Architecture Documentation

## System Overview

This is an in-memory Pub/Sub (Publish-Subscribe) system built with Python, FastAPI, and WebSockets. The system enables real-time message distribution across multiple subscribers with thread-safe concurrent operations.

## Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastAPI Application                      │
│                         (main.py)                            │
├──────────────────────┬──────────────────────────────────────┤
│  WebSocket Endpoint  │         REST API Endpoints           │
│       /ws            │  /topics, /health, /stats            │
└──────────────────────┴──────────────────────────────────────┘
                              │
                              ▼
                  ┌───────────────────────┐
                  │   PubSubManager       │
                  │  (pubsub_manager.py)  │
                  └───────────────────────┘
                              │
                 ┌────────────┴────────────┐
                 ▼                         ▼
           ┌─────────┐              ┌──────────┐
           │  Topic  │              │  Topic   │
           └─────────┘              └──────────┘
                 │                         │
         ┌───────┴────────┐        ┌───────┴────────┐
         ▼                ▼        ▼                ▼
    Subscriber1    Subscriber2  Subscriber3   Subscriber4
    (Queue)        (Queue)      (Queue)       (Queue)
```

## Core Components

### 1. Data Models ([models.py](models.py))

**Purpose**: Define all data structures using Pydantic for validation and serialization.

**Key Classes**:
- `ClientMessage`: Client → Server messages (subscribe, unsubscribe, publish, ping)
- `ServerMessage`: Server → Client messages (ack, event, error, pong, info)
- `Message`: Message payload with UUID and arbitrary JSON content
- REST API request/response models

**Benefits**:
- Type safety with Pydantic validation
- Automatic JSON serialization/deserialization
- Clear contract definition for WebSocket protocol

### 2. PubSub Manager ([pubsub_manager.py](pubsub_manager.py))

**Purpose**: Core business logic for managing topics, subscribers, and message distribution.

#### PubSubManager Class

**Responsibilities**:
- Topic lifecycle management (create, delete, list)
- Subscriber registration and management
- Message publishing and routing
- System statistics and observability

**Thread Safety**:
- Uses `asyncio.Lock` for protecting shared state
- Ensures atomic operations on topic registry
- Prevents race conditions in concurrent environments

**Key Methods**:
```python
async def create_topic(name: str) -> bool
async def delete_topic(name: str) -> bool
async def subscribe(topic_name, client_id, websocket, last_n) -> Optional[list]
async def unsubscribe(topic_name, client_id) -> bool
async def publish(topic_name, message) -> Optional[int]
```

#### Topic Class

**Responsibilities**:
- Maintain list of active subscribers
- Store message history for replay functionality
- Coordinate message fan-out to subscribers
- Track message statistics

**Key Features**:
- Circular buffer (deque) for message history
- Per-subscriber isolation
- Concurrent subscriber management with locks

**Key Methods**:
```python
async def add_subscriber(client_id, subscriber)
async def remove_subscriber(client_id) -> bool
async def publish_message(message) -> int
async def get_history(last_n) -> list
```

#### Subscriber Class

**Responsibilities**:
- Manage individual subscriber connection and queue
- Implement backpressure handling
- Track subscriber state (active/inactive)

**Key Features**:
- Bounded `asyncio.Queue` for message buffering
- Automatic oldest-message dropping on overflow
- Non-blocking enqueue operations

**Backpressure Policy**:
```python
# When queue is full:
1. Try to remove oldest message
2. Add new message
3. Log warning about dropped message
# This ensures slow consumers don't block publishers
```

### 3. FastAPI Application ([main.py](main.py))

**Purpose**: HTTP/WebSocket server exposing the Pub/Sub system.

#### WebSocket Endpoint (`/ws`)

**Message Handlers**:

1. **`handle_subscribe()`**
   - Validates topic existence
   - Creates Subscriber object
   - Registers with Topic
   - Sends historical messages if `last_n > 0`
   - Starts background message delivery task

2. **`handle_unsubscribe()`**
   - Removes subscriber from topic
   - Deactivates subscriber queue
   - Sends acknowledgment

3. **`handle_publish()`**
   - Validates message UUID format
   - Publishes to all subscribers (fan-out)
   - Tracks message in history
   - Sends acknowledgment

4. **`handle_ping()`**
   - Simple health check
   - Responds with pong

**Background Tasks**:
```python
async def message_sender_task(websocket, client_id, topic_name):
    # Continuously reads from subscriber queue
    # Sends messages via WebSocket
    # Runs until subscriber disconnects
```

#### REST Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/topics` | POST | Create new topic |
| `/topics/{name}` | DELETE | Delete topic and notify subscribers |
| `/topics` | GET | List all topics with subscriber counts |
| `/health` | GET | System health (uptime, topic count, subscriber count) |
| `/stats` | GET | Per-topic statistics (message count, subscriber count) |

### 4. Configuration ([config.py](config.py))

**Purpose**: Centralized configuration management with environment variable support.

**Key Parameters**:
- `MAX_SUBSCRIBER_QUEUE_SIZE`: Backpressure threshold (default: 100)
- `TOPIC_HISTORY_SIZE`: Replay buffer size (default: 100)
- `HOST`, `PORT`: Server binding
- `LOG_LEVEL`: Logging verbosity

**Environment Variables**:
```bash
PUBSUB_HOST=0.0.0.0
PUBSUB_PORT=8080
PUBSUB_MAX_QUEUE_SIZE=100
PUBSUB_HISTORY_SIZE=100
PUBSUB_LOG_LEVEL=INFO
```

## Data Flow

### Publish Flow

```
Publisher Client
    │
    │ 1. Send publish message via WebSocket
    ▼
WebSocket Handler (handle_publish)
    │
    │ 2. Validate message
    │ 3. Call pubsub_manager.publish()
    ▼
PubSubManager
    │
    │ 4. Acquire topic lock
    │ 5. Add to message history
    ▼
Topic.publish_message()
    │
    │ 6. Fan-out to all subscribers
    ├──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼
Subscriber1 Subscriber2 Subscriber3 ...
 Queue      Queue      Queue
    │          │          │
    │ 7. Background tasks read from queues
    ▼          ▼          ▼
WebSocket  WebSocket  WebSocket
    │          │          │
    │ 8. Deliver event messages
    ▼          ▼          ▼
Subscriber Subscriber Subscriber
  Clients    Clients    Clients
```

### Subscribe Flow

```
Client
    │
    │ 1. Send subscribe message
    ▼
WebSocket Handler (handle_subscribe)
    │
    │ 2. Validate topic exists
    │ 3. Call pubsub_manager.subscribe()
    ▼
PubSubManager
    │
    │ 4. Create Subscriber object
    │ 5. Add to topic's subscriber list
    ▼
Topic.add_subscriber()
    │
    │ 6. If last_n > 0, get history
    ▼
WebSocket Handler
    │
    │ 7. Send ack
    │ 8. Send historical messages
    │ 9. Start background message_sender_task
    ▼
Client receives:
    - ack
    - historical events (if any)
    - future events as they're published
```

## Concurrency Model

### Asyncio Event Loop

The system uses Python's `asyncio` for concurrent operations:

```python
# Single event loop handles:
- WebSocket connections
- HTTP requests
- Background message delivery tasks
- Queue operations
```

### Thread Safety Mechanisms

1. **Asyncio Locks**
   ```python
   async with self.lock:
       # Critical section - modify shared state
       self.topics[name] = Topic(name)
   ```

2. **Asyncio Queues**
   ```python
   # Thread-safe, async-compatible message queuing
   self.message_queue = asyncio.Queue(maxsize=100)
   ```

3. **Atomic Operations**
   - Topic creation/deletion
   - Subscriber registration/removal
   - Message publishing

### Scaling Considerations

**Current Design**:
- Single-process, single-machine
- Limited by Python GIL for CPU-bound operations
- Memory-bound by message history and queue sizes

**For Production Scale**:
- Use multiple uvicorn workers
- Add Redis for distributed state
- Implement topic sharding
- Add load balancer for WebSocket connections

## Message Guarantees

### Delivery Semantics

**At-Most-Once Delivery**:
- Messages are delivered to each subscriber at most once
- No retry mechanism
- Failed deliveries are logged but not retried

**Ordering**:
- Messages within a single publisher are ordered
- No global ordering guarantee across multiple publishers
- Subscribers receive messages in the order they were published to the topic

### Isolation Guarantees

1. **Topic Isolation**: Topics are completely independent
2. **Subscriber Isolation**: Each subscriber has its own queue
3. **No Cross-Talk**: Messages published to Topic A never reach subscribers of Topic B

## Backpressure Handling

### Problem

Slow subscribers can cause memory issues if queues grow unbounded.

### Solution

**Drop Oldest Message Policy**:

```python
if queue.full():
    oldest_message = queue.get_nowait()  # Drop
    queue.put_nowait(new_message)        # Add
```

**Alternative Approach** (not implemented):
```python
if queue.full():
    disconnect_subscriber()
    send_SLOW_CONSUMER_error()
```

**Trade-offs**:
- ✅ Keeps subscribers connected
- ✅ Guarantees recent message delivery
- ❌ May lose historical messages
- ❌ No notification of dropped messages

## Error Handling

### Error Codes

| Code | Scenario |
|------|----------|
| `BAD_REQUEST` | Invalid message format, missing fields, invalid UUID |
| `TOPIC_NOT_FOUND` | Subscribe/publish to non-existent topic |
| `SLOW_CONSUMER` | Subscriber queue overflow (if disconnect policy used) |
| `INTERNAL` | Unexpected server error |

### Error Propagation

```python
try:
    # Operation
except ValidationError:
    send_error(BAD_REQUEST, "Invalid message format")
except KeyError:
    send_error(TOPIC_NOT_FOUND, "Topic doesn't exist")
except Exception:
    send_error(INTERNAL, "Unexpected error")
    logger.exception("Unexpected error")
```

## Observability

### Metrics Collected

1. **System Level** (`/health`):
   - Uptime in seconds
   - Total topic count
   - Total subscriber count

2. **Topic Level** (`/stats`):
   - Per-topic message count
   - Per-topic subscriber count

### Logging

**Log Levels**:
- INFO: Connection events, topic operations, message flow
- WARNING: Backpressure events, subscription failures
- ERROR: Unexpected errors, validation failures

**Key Log Points**:
```python
logger.info("Topic created")
logger.warning("Queue full, dropping oldest message")
logger.error("Error in message sender task")
```

## Testing Strategy

### Unit Tests (Recommended)
- Test individual components in isolation
- Mock WebSocket connections
- Validate message formats

### Integration Tests
- Full end-to-end message flow
- Multiple concurrent subscribers
- Topic lifecycle operations

### Load Tests (Recommended)
- Stress test with many subscribers
- High-frequency message publishing
- Backpressure scenario validation

## Deployment

### Local Development
```bash
python main.py
```

### Docker Container
```bash
docker build -t pubsub-system .
docker run -p 8080:8080 pubsub-system
```

### Production Considerations
- Use process manager (systemd, supervisor)
- Configure reverse proxy (nginx, traefik)
- Set up monitoring (Prometheus, Grafana)
- Implement health checks
- Configure log aggregation

## Limitations

1. **No Persistence**: All data lost on restart
2. **Single Instance**: No clustering or replication
3. **In-Memory Only**: Limited by available RAM
4. **No Authentication**: Basic implementation (can be added)
5. **No Message Durability**: Messages not saved to disk
6. **Limited Replay**: Only last N messages available

## Future Enhancements

1. **Authentication**: JWT tokens or API keys
2. **Authorization**: Per-topic access control
3. **Persistence**: Optional Redis/PostgreSQL backend
4. **Message TTL**: Automatic message expiration
5. **Dead Letter Queue**: Failed delivery handling
6. **Metrics Export**: Prometheus endpoint
7. **Distributed Mode**: Multi-instance support
8. **Message Acknowledgments**: Ensure delivery guarantee
9. **Rate Limiting**: Per-client or per-topic limits
10. **WebSocket Compression**: Reduce bandwidth usage
