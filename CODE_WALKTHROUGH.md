# Complete Code Walkthrough

## Table of Contents
1. [System Initialization Flow](#system-initialization-flow)
2. [Data Models Deep Dive](#data-models-deep-dive)
3. [Core Classes Architecture](#core-classes-architecture)
4. [WebSocket Handler Flow](#websocket-handler-flow)
5. [REST API Handlers](#rest-api-handlers)
6. [Message Flow Diagrams](#message-flow-diagrams)

---

## System Initialization Flow

### 1. Application Startup ([main.py](main.py))

```python
# Step 1: Import dependencies and configuration
from config import config, print_config
from pubsub_manager import PubSubManager

# Step 2: Initialize global PubSubManager instance
pubsub_manager = PubSubManager()
# This is a SINGLETON - shared across all requests

# Step 3: Create FastAPI app with lifespan handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Pub/Sub service...")
    yield  # Application runs here
    logger.info("Shutting down Pub/Sub service...")
    # Could add cleanup logic here

app = FastAPI(
    title="Pub/Sub System",
    lifespan=lifespan  # Manages startup/shutdown
)

# Step 4: When run directly, start uvicorn server
if __name__ == "__main__":
    print_config()  # Print configuration
    uvicorn.run("main:app", host=config.HOST, port=config.PORT)
```

**What Happens:**
1. Configuration loaded from environment variables
2. Single `PubSubManager` instance created (holds all topics)
3. FastAPI app initialized with lifespan management
4. Uvicorn ASGI server starts, listening on port 8080

---

## Data Models Deep Dive

### Client → Server Messages ([models.py](models.py))

```python
class ClientMessage(BaseModel):
    type: Literal["subscribe", "unsubscribe", "publish", "ping"]
    topic: Optional[str] = None
    message: Optional[Message] = None
    client_id: Optional[str] = None
    last_n: Optional[int] = 0
    request_id: Optional[str] = None
```

**Field Validation:**
- `type`: Must be one of 4 specific strings (Pydantic enforces this)
- `topic`: Required for subscribe/unsubscribe/publish, validated in handlers
- `message`: Required for publish, contains `Message` object
- `client_id`: Required for subscribe/unsubscribe
- `last_n`: Optional, defaults to 0 (no replay)
- `request_id`: Optional correlation ID echoed back in responses

**Example Valid Message:**
```json
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "client-123",
  "last_n": 5,
  "request_id": "req-456"
}
```

### Server → Client Messages

```python
class ServerMessage(BaseModel):
    type: Literal["ack", "event", "error", "pong", "info"]
    request_id: Optional[str] = None  # Echoed from client
    topic: Optional[str] = None
    message: Optional[Message] = None
    error: Optional[ErrorDetail] = None
    status: Optional[str] = None
    msg: Optional[str] = None
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
```

**Automatic Timestamp:**
- `ts` field automatically set to current UTC time in ISO format
- Added to EVERY server message

---

## Core Classes Architecture

### Class Hierarchy

```
PubSubManager (Singleton)
    │
    ├── topics: Dict[str, Topic]
    │       │
    │       ├── Topic("orders")
    │       │     ├── subscribers: Dict[str, Subscriber]
    │       │     │     ├── Subscriber(client_id="sub1", websocket=...)
    │       │     │     │     └── message_queue: asyncio.Queue
    │       │     │     └── Subscriber(client_id="sub2", websocket=...)
    │       │     │           └── message_queue: asyncio.Queue
    │       │     └── message_history: deque (circular buffer)
    │       │
    │       └── Topic("notifications")
    │             └── subscribers: Dict[str, Subscriber]
    │
    └── lock: asyncio.Lock (protects topics dict)
```

---

### 1. PubSubManager Class ([pubsub_manager.py](pubsub_manager.py))

**Purpose:** Central manager coordinating all Pub/Sub operations

#### Constructor
```python
def __init__(self):
    self.topics: Dict[str, Topic] = {}
    self.lock = asyncio.Lock()  # Protects topics dict
    self.start_time = time.time()  # For uptime tracking
```

#### Key Methods with Flow

##### `create_topic(name: str) -> bool`

```python
async def create_topic(self, name: str) -> bool:
    async with self.lock:  # 1. Acquire lock (thread-safe)
        if name in self.topics:  # 2. Check if exists
            return False  # Already exists
        self.topics[name] = Topic(name)  # 3. Create new Topic
        return True  # Success
```

**Thread Safety:** The `async with self.lock` ensures only ONE coroutine can modify `self.topics` at a time.

##### `subscribe(topic_name, client_id, websocket, last_n) -> Optional[list]`

```python
async def subscribe(self, topic_name, client_id, websocket, last_n=0):
    # Step 1: Acquire lock and check topic exists
    async with self.lock:
        if topic_name not in self.topics:
            return None  # Topic not found
        topic = self.topics[topic_name]

    # Step 2: Create Subscriber object
    subscriber = Subscriber(client_id, websocket)

    # Step 3: Add to topic's subscriber list
    await topic.add_subscriber(client_id, subscriber)

    # Step 4: Get historical messages if requested
    history = []
    if last_n > 0:
        history = await topic.get_history(last_n)

    return history  # Return history for replay
```

**Why lock is released before adding subscriber:**
- We only need the lock to safely read `self.topics`
- Adding subscriber to topic uses the topic's own lock
- Reduces lock contention (better performance)

##### `publish(topic_name, message) -> Optional[int]`

```python
async def publish(self, topic_name, message):
    # Step 1: Get topic (with lock)
    async with self.lock:
        if topic_name not in self.topics:
            return None  # Topic not found
        topic = self.topics[topic_name]

    # Step 2: Publish to topic (topic has its own lock)
    return await topic.publish_message(message)
```

---

### 2. Topic Class ([pubsub_manager.py](pubsub_manager.py))

**Purpose:** Manages subscribers and messages for a single topic

#### Data Structures
```python
class Topic:
    HISTORY_SIZE = 100  # Configurable

    def __init__(self, name: str):
        self.name = name
        self.subscribers: Dict[str, Subscriber] = {}
        self.message_history: deque = deque(maxlen=100)  # Circular buffer
        self.message_count = 0
        self.lock = asyncio.Lock()  # Protects subscribers dict
```

**Circular Buffer:**
- `deque(maxlen=100)` automatically drops oldest when full
- O(1) append and retrieve operations
- Perfect for last_n replay

#### `publish_message(message) -> int`

```python
async def publish_message(self, message: Message) -> int:
    async with self.lock:
        # Step 1: Add to history
        self.message_history.append({
            'message': message,
            'ts': datetime.utcnow().isoformat() + "Z"
        })
        self.message_count += 1

        # Step 2: Fan-out to all subscribers
        success_count = 0
        for subscriber in self.subscribers.values():
            if subscriber.active:
                if await subscriber.enqueue_message(message, self.name):
                    success_count += 1

        return success_count
```

**Fan-Out Pattern:**
1. Message added to history ONCE
2. Iterate through ALL subscribers
3. Each subscriber gets message in their queue
4. Returns count of successful deliveries

**Why this is efficient:**
- Single message stored in history
- References passed to subscriber queues (not copies)
- Python's async nature prevents blocking

---

### 3. Subscriber Class ([pubsub_manager.py](pubsub_manager.py))

**Purpose:** Represents a single client subscription with message queue

#### Data Structures
```python
class Subscriber:
    MAX_QUEUE_SIZE = 100  # Configurable

    def __init__(self, client_id: str, websocket):
        self.client_id = client_id
        self.websocket = websocket
        self.message_queue = asyncio.Queue(maxsize=100)  # Bounded queue
        self.active = True
```

#### `enqueue_message(message, topic) -> bool`

```python
async def enqueue_message(self, message: Message, topic: str) -> bool:
    try:
        # Step 1: Try non-blocking put
        self.message_queue.put_nowait({
            'topic': topic,
            'message': message,
            'ts': datetime.utcnow().isoformat() + "Z"
        })
        return True

    except asyncio.QueueFull:
        # Step 2: Backpressure - drop oldest, add new
        logger.warning(f"Queue full for {self.client_id}")
        try:
            self.message_queue.get_nowait()  # Remove oldest
            self.message_queue.put_nowait({...})  # Add new
            return True
        except Exception as e:
            logger.error(f"Backpressure error: {e}")
            return False
```

**Backpressure Policy Explained:**

```
Normal Flow:
┌────────┐  ┌────────┐  ┌────────┐     ┌─────┐
│ Msg 1  │  │ Msg 2  │  │ Msg 3  │ ... │Empty│
└────────┘  └────────┘  └────────┘     └─────┘
   ↑                                       ↑
  Oldest                                 Newest (add here)

Queue Full:
┌────────┐  ┌────────┐  ┌────────┐     ┌────────┐
│ Msg 1  │  │ Msg 2  │  │ Msg 3  │ ... │ Msg 100│
└────────┘  └────────┘  └────────┘     └────────┘
   ↑ DROP THIS                             ↑

After Backpressure:
┌────────┐  ┌────────┐  ┌────────┐     ┌────────┐
│ Msg 2  │  │ Msg 3  │  │ Msg 4  │ ... │ Msg 101│ ← New msg added
└────────┘  └────────┘  └────────┘     └────────┘
```

**Why Drop Oldest:**
- Real-time systems care about RECENT data
- Slow consumer shouldn't block fast publishers
- Keeps subscriber connected (no disconnect)

---

## WebSocket Handler Flow

### Connection Lifecycle

```python
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Step 1: Accept connection
    await websocket.accept()
    logger.info("WebSocket connection established")

    try:
        while True:  # Step 2: Message loop
            # Receive JSON from client
            data = await websocket.receive_json()

            try:
                # Parse with Pydantic (auto-validation)
                msg = ClientMessage(**data)

                # Route to appropriate handler
                if msg.type == "subscribe":
                    await handle_subscribe(websocket, msg)
                elif msg.type == "unsubscribe":
                    await handle_unsubscribe(websocket, msg)
                elif msg.type == "publish":
                    await handle_publish(websocket, msg)
                elif msg.type == "ping":
                    await handle_ping(websocket, msg)

            except Exception as e:
                # Validation or handler error
                await send_error(websocket, ErrorCode.BAD_REQUEST, str(e))

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed")
    finally:
        logger.info("WebSocket connection terminated")
```

---

### Handler: `handle_subscribe`

**Complete Flow with Example:**

```python
async def handle_subscribe(websocket: WebSocket, msg: ClientMessage):
    # ============================================================
    # STEP 1: Validate required fields
    # ============================================================
    if not msg.topic:
        await send_error(websocket, ErrorCode.BAD_REQUEST,
                        "topic is required", msg.request_id)
        return

    if not msg.client_id:
        await send_error(websocket, ErrorCode.BAD_REQUEST,
                        "client_id is required", msg.request_id)
        return

    # ============================================================
    # STEP 2: Subscribe via PubSubManager
    # ============================================================
    history = await pubsub_manager.subscribe(
        topic_name=msg.topic,
        client_id=msg.client_id,
        websocket=websocket,
        last_n=msg.last_n or 0
    )

    if history is None:
        # Topic doesn't exist
        await send_error(websocket, ErrorCode.TOPIC_NOT_FOUND,
                        f"Topic '{msg.topic}' does not exist",
                        msg.request_id)
        return

    # ============================================================
    # STEP 3: Send acknowledgment
    # ============================================================
    await send_ack(websocket, topic=msg.topic, request_id=msg.request_id)
    # Client receives: {"type": "ack", "topic": "orders",
    #                   "status": "ok", "ts": "2025-..."}

    # ============================================================
    # STEP 4: Send historical messages (if last_n > 0)
    # ============================================================
    if history:
        for hist_msg in history:
            event_msg = ServerMessage(
                type="event",
                topic=msg.topic,
                message=hist_msg['message'],
                ts=hist_msg['ts']
            )
            await websocket.send_json(event_msg.model_dump(exclude_none=True))

    # ============================================================
    # STEP 5: Start background task to deliver future messages
    # ============================================================
    asyncio.create_task(message_sender_task(websocket, msg.client_id, msg.topic))
```

**Example Flow:**

```
Client sends:
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "client-1",
  "last_n": 3,
  "request_id": "req-123"
}

Server responds:
1. {"type": "ack", "request_id": "req-123", "topic": "orders",
    "status": "ok", "ts": "2025-01-30T10:00:00Z"}

2. {"type": "event", "topic": "orders",
    "message": {"id": "...", "payload": {...}},
    "ts": "2025-01-30T09:58:00Z"}  // Historical msg 1

3. {"type": "event", "topic": "orders",
    "message": {"id": "...", "payload": {...}},
    "ts": "2025-01-30T09:59:00Z"}  // Historical msg 2

4. {"type": "event", "topic": "orders",
    "message": {"id": "...", "payload": {...}},
    "ts": "2025-01-30T09:59:30Z"}  // Historical msg 3

5. Background task starts, delivers future messages...
```

---

### Background Task: `message_sender_task`

**Purpose:** Continuously reads from subscriber's queue and sends via WebSocket

```python
async def message_sender_task(websocket, client_id, topic_name):
    # Step 1: Get subscriber object
    if not pubsub_manager.topic_exists(topic_name):
        return

    topic = pubsub_manager.topics[topic_name]
    if client_id not in topic.subscribers:
        return

    subscriber = topic.subscribers[client_id]

    # Step 2: Infinite loop - read and send
    try:
        while subscriber.active:
            # BLOCKING wait for next message
            msg_data = await subscriber.get_message()

            # Build event message
            event_msg = ServerMessage(
                type="event",
                topic=msg_data['topic'],
                message=msg_data['message'],
                ts=msg_data['ts']
            )

            # Send via WebSocket
            await websocket.send_json(event_msg.model_dump(exclude_none=True))

    except Exception as e:
        logger.error(f"Error in sender task: {e}")
    finally:
        logger.info(f"Sender task ended for {client_id}")
```

**Why Background Task:**
- Subscriber receives messages via WebSocket connection
- Main handler returns immediately after subscribe
- Background task runs INDEPENDENTLY
- One task per subscriber per topic

**Lifecycle:**
```
Subscribe → Background task starts
    ↓
Messages published → Added to queue
    ↓
Background task reads queue → Sends via WebSocket
    ↓
Unsubscribe/Disconnect → subscriber.active = False → Task exits
```

---

### Handler: `handle_publish`

```python
async def handle_publish(websocket: WebSocket, msg: ClientMessage):
    # ============================================================
    # STEP 1: Validate required fields
    # ============================================================
    if not msg.topic:
        await send_error(websocket, ErrorCode.BAD_REQUEST,
                        "topic is required", msg.request_id)
        return

    if not msg.message:
        await send_error(websocket, ErrorCode.BAD_REQUEST,
                        "message is required", msg.request_id)
        return

    # ============================================================
    # STEP 2: Validate UUID format
    # ============================================================
    try:
        uuid.UUID(msg.message.id)
    except ValueError:
        await send_error(websocket, ErrorCode.BAD_REQUEST,
                        "message.id must be a valid UUID",
                        msg.request_id)
        return

    # ============================================================
    # STEP 3: Publish to topic
    # ============================================================
    subscriber_count = await pubsub_manager.publish(msg.topic, msg.message)

    if subscriber_count is None:
        # Topic not found
        await send_error(websocket, ErrorCode.TOPIC_NOT_FOUND,
                        f"Topic '{msg.topic}' does not exist",
                        msg.request_id)
        return

    # ============================================================
    # STEP 4: Send acknowledgment
    # ============================================================
    await send_ack(websocket, topic=msg.topic, request_id=msg.request_id)
```

**Complete Publish Flow:**

```
Publisher                Topic               Subscribers
    │                      │                      │
    │  1. Publish msg      │                      │
    ├─────────────────────>│                      │
    │                      │                      │
    │                      │ 2. Add to history    │
    │                      │    Increment counter │
    │                      │                      │
    │                      │ 3. Fan-out           │
    │                      ├─────────────────────>│ Sub1: enqueue
    │                      ├─────────────────────>│ Sub2: enqueue
    │                      ├─────────────────────>│ Sub3: enqueue
    │                      │                      │
    │  4. Send ack         │                      │
    │<─────────────────────┤                      │
    │                      │                      │
    │                      │ 5. Background tasks  │
    │                      │    read queues       │
    │                      │                      │
    │                      │                   ┌──┴───┐
    │                      │                   │ Send │
    │                      │                   │ event│
    │                      │                   └──────┘
```

---

### Handler: `handle_unsubscribe`

```python
async def handle_unsubscribe(websocket: WebSocket, msg: ClientMessage):
    # Validate fields
    if not msg.topic or not msg.client_id:
        await send_error(...)
        return

    # Unsubscribe
    success = await pubsub_manager.unsubscribe(msg.topic, msg.client_id)

    if not success:
        await send_error(websocket, ErrorCode.TOPIC_NOT_FOUND, ...)
        return

    # Send ack
    await send_ack(websocket, topic=msg.topic, request_id=msg.request_id)
```

**What Happens:**
1. Subscriber removed from topic's subscriber dict
2. `subscriber.active = False` (stops background task)
3. Background task exits gracefully
4. Acknowledgment sent to client

---

### Handler: `handle_ping`

```python
async def handle_ping(websocket: WebSocket, msg: ClientMessage):
    await send_pong(websocket, request_id=msg.request_id)
```

**Simple health check:**
```
Client → {"type": "ping", "request_id": "ping-123"}
Server → {"type": "pong", "request_id": "ping-123", "ts": "2025-01-30..."}
```

---

## REST API Handlers

### 1. `POST /topics` - Create Topic

```python
@app.post("/topics", response_model=CreateTopicResponse,
          status_code=status.HTTP_201_CREATED)
async def create_topic(request: CreateTopicRequest):
    # Step 1: Call PubSubManager
    success = await pubsub_manager.create_topic(request.name)

    # Step 2: Return 409 if already exists
    if not success:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Topic '{request.name}' already exists"
        )

    # Step 3: Return 201 Created
    return CreateTopicResponse(topic=request.name)
```

**Example:**
```bash
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name": "orders"}'

# Success (201):
{"status": "created", "topic": "orders"}

# Already exists (409):
{"detail": "Topic 'orders' already exists"}
```

---

### 2. `DELETE /topics/{name}` - Delete Topic

```python
@app.delete("/topics/{name}", response_model=DeleteTopicResponse)
async def delete_topic(name: str):
    # Step 1: Delete topic
    success = await pubsub_manager.delete_topic(name)

    # Step 2: Return 404 if not found
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topic '{name}' not found"
        )

    # Step 3: Return 200 OK
    return DeleteTopicResponse(topic=name)
```

**What happens in `delete_topic`:**
```python
async def delete_topic(self, name: str) -> bool:
    async with self.lock:
        if name not in self.topics:
            return False

        topic = self.topics[name]

        # Notify all subscribers
        for subscriber in topic.subscribers.values():
            try:
                info_msg = ServerMessage(
                    type="info",
                    topic=name,
                    msg="topic_deleted"
                )
                await subscriber.websocket.send_json(
                    info_msg.model_dump(exclude_none=True)
                )
            except Exception as e:
                logger.error(f"Error notifying subscriber: {e}")

        # Remove topic
        del self.topics[name]
        return True
```

**Subscriber receives:**
```json
{
  "type": "info",
  "topic": "orders",
  "msg": "topic_deleted",
  "ts": "2025-01-30T10:00:00Z"
}
```

---

### 3. `GET /topics` - List Topics

```python
@app.get("/topics", response_model=ListTopicsResponse)
async def list_topics():
    # Step 1: Get all topics
    topics_data = await pubsub_manager.get_all_topics()

    # Step 2: Convert to Pydantic models
    topics = [TopicInfo(name=t['name'], subscribers=t['subscribers'])
              for t in topics_data]

    # Step 3: Return response
    return ListTopicsResponse(topics=topics)
```

**Example Response:**
```json
{
  "topics": [
    {"name": "orders", "subscribers": 3},
    {"name": "notifications", "subscribers": 1},
    {"name": "events", "subscribers": 0}
  ]
}
```

---

### 4. `GET /health` - Health Check

```python
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(
        uptime_sec=pubsub_manager.get_uptime(),  # time.time() - start_time
        topics=len(pubsub_manager.topics),
        subscribers=pubsub_manager.get_total_subscribers()
    )
```

**Example Response:**
```json
{
  "uptime_sec": 3600,
  "topics": 5,
  "subscribers": 12
}
```

---

### 5. `GET /stats` - Statistics

```python
@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    # Get per-topic stats
    stats_data = await pubsub_manager.get_stats()

    # Convert to response model
    topics_stats = {
        name: TopicStats(messages=data['messages'],
                        subscribers=data['subscribers'])
        for name, data in stats_data.items()
    }

    return StatsResponse(topics=topics_stats)
```

**Example Response:**
```json
{
  "topics": {
    "orders": {
      "messages": 1523,
      "subscribers": 3
    },
    "notifications": {
      "messages": 45,
      "subscribers": 1
    }
  }
}
```

---

## Message Flow Diagrams

### Complete Subscribe → Publish → Receive Flow

```
Time →

T1: Client1 connects to WebSocket
    ├─> send: {"type": "subscribe", "topic": "orders", "client_id": "c1"}
    ├─> receive: {"type": "ack", ...}
    └─> Background task starts listening to queue

T2: Client2 connects to WebSocket
    ├─> send: {"type": "subscribe", "topic": "orders", "client_id": "c2"}
    ├─> receive: {"type": "ack", ...}
    └─> Background task starts listening to queue

T3: Publisher connects and publishes
    ├─> send: {"type": "publish", "topic": "orders", "message": {...}}
    │
    ├─> PubSubManager.publish()
    │   └─> Topic.publish_message()
    │       ├─> Add to message_history
    │       ├─> Subscriber(c1).enqueue_message() → Queue[c1]
    │       └─> Subscriber(c2).enqueue_message() → Queue[c2]
    │
    └─> receive: {"type": "ack", ...}

T4: Background tasks detect messages in queues
    ├─> Task[c1]: read from Queue[c1]
    │   └─> websocket[c1].send({"type": "event", ...})
    │
    └─> Task[c2]: read from Queue[c2]
        └─> websocket[c2].send({"type": "event", ...})

T5: Client1 receives event
    └─> {"type": "event", "topic": "orders", "message": {...}}

T6: Client2 receives event
    └─> {"type": "event", "topic": "orders", "message": {...}}
```

---

### Error Handling Flow

```
Client sends invalid message:
{"type": "publish", "topic": "orders", "message": {"id": "not-a-uuid"}}
    │
    ├─> websocket_endpoint receives
    │   └─> ClientMessage(**data) ✓ (Pydantic validates structure)
    │
    ├─> handle_publish()
    │   ├─> Check topic ✓
    │   ├─> Check message ✓
    │   └─> Validate UUID ✗ → ValueError raised
    │
    ├─> send_error(ErrorCode.BAD_REQUEST, "message.id must be valid UUID")
    │
    └─> Client receives:
        {
          "type": "error",
          "error": {
            "code": "BAD_REQUEST",
            "message": "message.id must be a valid UUID"
          },
          "ts": "2025-01-30T10:00:00Z"
        }
```

---

## Concurrency and Thread Safety

### Lock Hierarchy

```
PubSubManager.lock
    ↓ (protects topics dict)
    Topics created/deleted here

Topic.lock
    ↓ (protects subscribers dict and message_history)
    Subscribers added/removed, messages published here

Subscriber.message_queue
    ↓ (asyncio.Queue is inherently thread-safe)
    Messages enqueued/dequeued here
```

### Example Concurrent Scenario

```
Coroutine 1: create_topic("orders")
    │ Acquires PubSubManager.lock
    │ Creates Topic
    │ Releases PubSubManager.lock

Coroutine 2: subscribe("orders", "c1", ...)
    │ Waits for PubSubManager.lock...
    │ Acquires PubSubManager.lock
    │ Reads topics["orders"]
    │ Releases PubSubManager.lock
    │ Acquires Topic.lock
    │ Adds subscriber
    │ Releases Topic.lock

Coroutine 3: publish("orders", message)
    │ Acquires PubSubManager.lock
    │ Reads topics["orders"]
    │ Releases PubSubManager.lock
    │ Acquires Topic.lock
    │ Publishes message
    │ Releases Topic.lock
```

**Key Points:**
- Locks held for MINIMUM time
- Read operations also acquire locks (consistency)
- Asyncio ensures no true parallelism (GIL)
- But allows interleaved execution (concurrency)

---

## Configuration System

### Environment Variable Loading ([config.py](config.py))

```python
class Config:
    HOST = os.getenv("PUBSUB_HOST", "0.0.0.0")
    PORT = int(os.getenv("PUBSUB_PORT", "8080"))
    LOG_LEVEL = os.getenv("PUBSUB_LOG_LEVEL", "INFO")
    MAX_SUBSCRIBER_QUEUE_SIZE = int(os.getenv("PUBSUB_MAX_QUEUE_SIZE", "100"))
    TOPIC_HISTORY_SIZE = int(os.getenv("PUBSUB_HISTORY_SIZE", "100"))

config = Config()  # Singleton instance
```

### Usage Throughout Code

```python
# In pubsub_manager.py
from config import config

class Subscriber:
    MAX_QUEUE_SIZE = config.MAX_SUBSCRIBER_QUEUE_SIZE  # From env var

class Topic:
    HISTORY_SIZE = config.TOPIC_HISTORY_SIZE  # From env var

# In main.py
uvicorn.run("main:app", host=config.HOST, port=config.PORT)
```

### Customization

```bash
# Set custom config
export PUBSUB_PORT=9000
export PUBSUB_MAX_QUEUE_SIZE=200
export PUBSUB_LOG_LEVEL=DEBUG

# Run server
python main.py
```

---

## Summary: Request Flow

### WebSocket Subscribe
```
Client → WebSocket /ws → handle_subscribe() → PubSubManager.subscribe()
→ Topic.add_subscriber() → Create Subscriber → Start background task
→ Send ack → Send history (if last_n) → Background task delivers future messages
```

### WebSocket Publish
```
Client → WebSocket /ws → handle_publish() → Validate UUID
→ PubSubManager.publish() → Topic.publish_message() → Add to history
→ Fan-out to all subscribers → Enqueue in each subscriber's queue
→ Send ack → Background tasks deliver to WebSockets
```

### REST Create Topic
```
Client → POST /topics → create_topic() → PubSubManager.create_topic()
→ Check exists → Create Topic object → Add to topics dict → Return 201
```

### REST Delete Topic
```
Client → DELETE /topics/{name} → delete_topic() → PubSubManager.delete_topic()
→ Get topic → Notify all subscribers (send info message) → Delete topic → Return 200
```

---

This walkthrough shows how every component works together to create a robust, thread-safe, real-time Pub/Sub system!
