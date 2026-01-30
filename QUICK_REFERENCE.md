# Quick Reference Card

## 🚀 Start Server

```bash
python main.py
# Server starts on http://localhost:8080
```

## 📡 REST API Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Create topic
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name":"orders"}'

# List topics
curl http://localhost:8080/topics

# Delete topic
curl -X DELETE http://localhost:8080/topics/orders

# Get statistics
curl http://localhost:8080/stats
```

## 🔌 WebSocket Messages

### Subscribe
```json
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "client-1"
}
```

### Subscribe with Replay
```json
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "client-1",
  "last_n": 5
}
```

### Publish
```json
{
  "type": "publish",
  "topic": "orders",
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {"order_id": "ORD-123", "amount": 99.5}
  }
}
```

### Unsubscribe
```json
{
  "type": "unsubscribe",
  "topic": "orders",
  "client_id": "client-1"
}
```

### Ping
```json
{
  "type": "ping"
}
```

## 🧪 Quick Test

```bash
# Terminal 1: Start server
python main.py

# Terminal 2: Run tests
python test_pubsub.py

# Terminal 3: Interactive client
python example_client.py
```

## 🐳 Docker

```bash
# Build
docker build -t pubsub-system .

# Run
docker run -p 8080:8080 pubsub-system
```

## 🔧 Configuration

```bash
export PUBSUB_HOST=0.0.0.0
export PUBSUB_PORT=8080
export PUBSUB_MAX_QUEUE_SIZE=100
export PUBSUB_HISTORY_SIZE=100
export PUBSUB_LOG_LEVEL=INFO
```

## 🎯 Common UUIDs for Testing

```
550e8400-e29b-41d4-a716-446655440000
650e8400-e29b-41d4-a716-446655440001
750e8400-e29b-41d4-a716-446655440002
```

Generate UUID: `python -c "import uuid; print(uuid.uuid4())"`

## ⚠️ Error Codes

- `BAD_REQUEST` - Invalid message or missing fields
- `TOPIC_NOT_FOUND` - Topic doesn't exist
- `SLOW_CONSUMER` - Queue overflow
- `INTERNAL` - Server error

## 📚 Documentation Files

- **QUICKSTART.md** - 5-minute setup guide
- **CODE_WALKTHROUGH.md** - Complete code explanation ⭐
- **TESTING_GUIDE.md** - How to test everything ⭐
- **VISUAL_GUIDE.md** - System diagrams
- **ARCHITECTURE.md** - Deep dive
- **README.md** - Full API reference

## 🔗 WebSocket Testing Tools

```bash
# wscat
npm install -g wscat
wscat -c ws://localhost:8080/ws

# Python
python example_client.py

# Postman
Import: PubSub_Postman_Collection.json
```

## 📊 File Structure

```
main.py              - FastAPI app & routes
pubsub_manager.py    - Core Pub/Sub logic
models.py            - Pydantic data models
config.py            - Configuration
test_pubsub.py       - Automated tests
example_client.py    - Interactive client
Dockerfile           - Docker build
requirements.txt     - Dependencies
```

## 💡 Key Classes

```python
PubSubManager        # Central coordinator (singleton)
  ├── create_topic()
  ├── delete_topic()
  ├── subscribe()
  ├── unsubscribe()
  └── publish()

Topic                # Manages subscribers per topic
  ├── add_subscriber()
  ├── remove_subscriber()
  └── publish_message()  # Fan-out

Subscriber           # Individual client subscription
  ├── enqueue_message()  # Backpressure handling
  └── get_message()
```

## 🎓 Message Flow

```
1. Client subscribes → Creates Subscriber → Starts background task
2. Publisher publishes → Adds to history → Fan-out to all queues
3. Background tasks read queues → Send events via WebSocket
```

## ⚡ Quick Commands

```bash
# Helper script
./run.sh install     # Install dependencies
./run.sh server      # Start server
./run.sh test        # Run tests
./run.sh client      # Interactive client
./run.sh health      # Health check
./run.sh stats       # Statistics
./run.sh demo        # Quick demo
```

## 🐛 Troubleshooting

**Connection refused?** → Start server: `python main.py`

**Topic not found?** → Create topic first: `POST /topics`

**Invalid UUID?** → Use valid UUID format (see above)

**WebSocket closes?** → Check server logs, validate JSON
