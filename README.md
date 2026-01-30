# In-Memory Pub/Sub System

A simplified in-memory publish-subscribe system built with Python and FastAPI. This system provides WebSocket-based real-time messaging and REST APIs for topic management and observability.

## Features

- **WebSocket-based Pub/Sub**: Real-time message publishing and subscription over `/ws` endpoint
- **Topic Management**: Create, delete, and list topics via REST APIs
- **Message Replay**: Support for replaying last N historical messages on subscription
- **Backpressure Handling**: Automatic handling of slow consumers with configurable queue limits
- **Observability**: Health checks and statistics endpoints
- **Thread-Safe**: Concurrent publisher and subscriber support with asyncio locks
- **In-Memory**: No external dependencies (Redis, Kafka, RabbitMQ)
- **Docker Support**: Containerized deployment

## Architecture

### Components

1. **models.py**: Pydantic models for all message structures and API schemas
2. **pubsub_manager.py**: Core Pub/Sub logic with Topic and Subscriber management
3. **main.py**: FastAPI application with WebSocket and REST endpoints

### Design Decisions

**Backpressure Policy**: When a subscriber's queue reaches capacity (100 messages), the system drops the **oldest message** and adds the new one. This ensures slow consumers don't cause memory issues while maintaining real-time delivery of recent messages.

**Message History**: Each topic maintains a circular buffer of the last 100 messages for replay functionality (`last_n` parameter).

**Concurrency**: Uses asyncio locks for thread-safe operations on shared data structures (topics, subscribers).

**Isolation**: Each topic maintains its own subscriber list and message history, ensuring no cross-topic interference.

## Requirements

- Python 3.10+
- FastAPI
- Uvicorn
- WebSockets
- Pydantic

## Installation

### Local Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd plivo-assignment-2
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the server:
```bash
python main.py
```

The server will start on `http://localhost:8080`

### Docker Setup

1. Build the Docker image:
```bash
docker build -t pubsub-system .
```

2. Run the container:
```bash
docker run -p 8080:8080 pubsub-system
```

## API Documentation

### WebSocket Endpoint: `/ws`

#### Client → Server Messages

##### Subscribe
```json
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "subscriber-1",
  "last_n": 5,
  "request_id": "uuid-optional"
}
```

##### Unsubscribe
```json
{
  "type": "unsubscribe",
  "topic": "orders",
  "client_id": "subscriber-1",
  "request_id": "uuid-optional"
}
```

##### Publish
```json
{
  "type": "publish",
  "topic": "orders",
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "order_id": "ORD-123",
      "amount": 99.5,
      "currency": "USD"
    }
  },
  "request_id": "uuid-optional"
}
```

##### Ping
```json
{
  "type": "ping",
  "request_id": "uuid-optional"
}
```

#### Server → Client Messages

##### Acknowledgment (ack)
```json
{
  "type": "ack",
  "request_id": "uuid",
  "topic": "orders",
  "status": "ok",
  "ts": "2025-08-25T10:00:00Z"
}
```

##### Event (message delivery)
```json
{
  "type": "event",
  "topic": "orders",
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {...}
  },
  "ts": "2025-08-25T10:01:00Z"
}
```

##### Error
```json
{
  "type": "error",
  "request_id": "uuid",
  "error": {
    "code": "TOPIC_NOT_FOUND",
    "message": "Topic 'orders' does not exist"
  },
  "ts": "2025-08-25T10:02:00Z"
}
```

**Error Codes**:
- `BAD_REQUEST`: Invalid message format or missing required fields
- `TOPIC_NOT_FOUND`: Topic doesn't exist
- `SLOW_CONSUMER`: Subscriber queue overflow
- `INTERNAL`: Server error

##### Pong
```json
{
  "type": "pong",
  "request_id": "uuid",
  "ts": "2025-08-25T10:03:00Z"
}
```

##### Info
```json
{
  "type": "info",
  "topic": "orders",
  "msg": "topic_deleted",
  "ts": "2025-08-25T10:05:00Z"
}
```

### REST API Endpoints

#### Create Topic
```http
POST /topics
Content-Type: application/json

{
  "name": "orders"
}
```

**Response** (201 Created):
```json
{
  "status": "created",
  "topic": "orders"
}
```

**Error** (409 Conflict): Topic already exists

#### Delete Topic
```http
DELETE /topics/orders
```

**Response** (200 OK):
```json
{
  "status": "deleted",
  "topic": "orders"
}
```

**Error** (404 Not Found): Topic doesn't exist

#### List Topics
```http
GET /topics
```

**Response** (200 OK):
```json
{
  "topics": [
    {
      "name": "orders",
      "subscribers": 3
    },
    {
      "name": "notifications",
      "subscribers": 1
    }
  ]
}
```

#### Health Check
```http
GET /health
```

**Response** (200 OK):
```json
{
  "uptime_sec": 123,
  "topics": 2,
  "subscribers": 4
}
```

#### Statistics
```http
GET /stats
```

**Response** (200 OK):
```json
{
  "topics": {
    "orders": {
      "messages": 42,
      "subscribers": 3
    },
    "notifications": {
      "messages": 15,
      "subscribers": 1
    }
  }
}
```

## Usage Examples

### Using Python WebSocket Client

```python
import asyncio
import json
import websockets

async def test_pubsub():
    uri = "ws://localhost:8080/ws"

    async with websockets.connect(uri) as websocket:
        # Subscribe to topic
        subscribe_msg = {
            "type": "subscribe",
            "topic": "orders",
            "client_id": "test-subscriber",
            "last_n": 0
        }
        await websocket.send(json.dumps(subscribe_msg))

        # Wait for acknowledgment
        response = await websocket.recv()
        print(f"Subscribe response: {response}")

        # Publish a message
        publish_msg = {
            "type": "publish",
            "topic": "orders",
            "message": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "payload": {"order_id": "ORD-123", "amount": 99.5}
            }
        }
        await websocket.send(json.dumps(publish_msg))

        # Receive messages
        while True:
            message = await websocket.recv()
            print(f"Received: {message}")

asyncio.run(test_pubsub())
```

### Using cURL for REST APIs

```bash
# Create a topic
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name": "orders"}'

# List topics
curl http://localhost:8080/topics

# Get health status
curl http://localhost:8080/health

# Get statistics
curl http://localhost:8080/stats

# Delete topic
curl -X DELETE http://localhost:8080/topics/orders
```

## Testing

### Manual Testing with wscat

Install wscat:
```bash
npm install -g wscat
```

Connect and test:
```bash
# Connect to WebSocket
wscat -c ws://localhost:8080/ws

# Subscribe
> {"type": "subscribe", "topic": "test", "client_id": "client1"}

# Publish (in another terminal)
> {"type": "publish", "topic": "test", "message": {"id": "550e8400-e29b-41d4-a716-446655440000", "payload": "Hello"}}

# Ping
> {"type": "ping", "request_id": "test-ping"}

# Unsubscribe
> {"type": "unsubscribe", "topic": "test", "client_id": "client1"}
```

## Configuration

Key configuration parameters in `pubsub_manager.py`:

- `Subscriber.MAX_QUEUE_SIZE`: Maximum messages per subscriber queue (default: 100)
- `Topic.HISTORY_SIZE`: Number of historical messages to retain (default: 100)

Server configuration in `main.py`:

- Host: `0.0.0.0`
- Port: `8080`

## Limitations

- **In-memory only**: All data is lost on restart (no persistence)
- **Single instance**: No distributed deployment support
- **No authentication**: Basic implementation without auth (can be added as stretch goal)
- **No message ordering guarantees**: Under high concurrency, message order may vary
- **Limited scalability**: Bounded by single machine's memory and CPU

## Future Enhancements

- [ ] Add X-API-Key authentication for REST and WebSocket
- [ ] Implement message persistence (optional Redis backend)
- [ ] Add Prometheus metrics endpoint
- [ ] Implement subscriber connection pooling
- [ ] Add rate limiting per topic/subscriber
- [ ] Support for message TTL (time-to-live)
- [ ] Add topic partitioning for scalability

## License

MIT License

## Author

Technical Assignment for Plivo
