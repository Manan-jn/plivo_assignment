# Quick Start Guide

This guide will help you get the Pub/Sub system running in under 5 minutes.

## Prerequisites

- Python 3.10 or higher
- pip package manager
- (Optional) Docker for containerized deployment

## Method 1: Local Installation

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Start the Server

```bash
python main.py
```

You should see:
```
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

### Step 3: Verify Server is Running

Open a new terminal and run:

```bash
curl http://localhost:8080/health
```

Expected response:
```json
{
  "uptime_sec": 5,
  "topics": 0,
  "subscribers": 0
}
```

## Method 2: Docker

### Step 1: Build the Image

```bash
docker build -t pubsub-system .
```

### Step 2: Run the Container

```bash
docker run -p 8080:8080 pubsub-system
```

## Testing the System

### Quick Test with cURL

```bash
# Create a topic
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name": "demo"}'

# List topics
curl http://localhost:8080/topics

# Get statistics
curl http://localhost:8080/stats
```

### Run the Comprehensive Test Suite

In a new terminal (while the server is running):

```bash
python test_pubsub.py
```

This will run all tests including:
- REST API operations
- Pub/Sub message flow with multiple subscribers
- Message replay functionality
- Ping/pong
- Error handling
- Topic deletion

### Interactive Example Client

For a hands-on experience:

```bash
python example_client.py
```

This provides an interactive menu to:
1. Run as a subscriber (listen for messages)
2. Run as a publisher (send messages)
3. Test ping/pong

## Common Operations

### Create a Topic (REST API)

```bash
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name": "orders"}'
```

### Subscribe via WebSocket (Python)

```python
import asyncio
import json
import websockets

async def subscribe():
    async with websockets.connect("ws://localhost:8080/ws") as ws:
        msg = {
            "type": "subscribe",
            "topic": "orders",
            "client_id": "my-subscriber"
        }
        await ws.send(json.dumps(msg))

        while True:
            response = await ws.recv()
            print(response)

asyncio.run(subscribe())
```

### Publish a Message via WebSocket (Python)

```python
import asyncio
import json
import websockets
import uuid

async def publish():
    async with websockets.connect("ws://localhost:8080/ws") as ws:
        msg = {
            "type": "publish",
            "topic": "orders",
            "message": {
                "id": str(uuid.uuid4()),
                "payload": {"order_id": "ORD-123", "amount": 99.5}
            }
        }
        await ws.send(json.dumps(msg))
        ack = await ws.recv()
        print(ack)

asyncio.run(publish())
```

### Using wscat (Node.js WebSocket CLI)

Install wscat:
```bash
npm install -g wscat
```

Connect and interact:
```bash
wscat -c ws://localhost:8080/ws
```

Then send messages:
```json
{"type": "ping"}
{"type": "subscribe", "topic": "demo", "client_id": "test1"}
{"type": "publish", "topic": "demo", "message": {"id": "550e8400-e29b-41d4-a716-446655440000", "payload": "Hello"}}
```

## Monitoring

### Health Check

```bash
curl http://localhost:8080/health
```

### System Statistics

```bash
curl http://localhost:8080/stats
```

### List All Topics

```bash
curl http://localhost:8080/topics
```

## Stopping the Server

### Local Installation
Press `Ctrl+C` in the terminal where the server is running.

### Docker
```bash
docker ps  # Find the container ID
docker stop <container-id>
```

## Troubleshooting

### Port Already in Use

If port 8080 is already in use, you can change it in `main.py`:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8081)  # Changed to 8081
```

### Connection Refused

Make sure the server is running before trying to connect clients.

### WebSocket Connection Issues

Ensure your WebSocket client supports the `ws://` protocol (not `wss://` for local testing).

## Next Steps

- Read the full [README.md](README.md) for detailed API documentation
- Explore the code:
  - [models.py](models.py) - Data models
  - [pubsub_manager.py](pubsub_manager.py) - Core Pub/Sub logic
  - [main.py](main.py) - FastAPI application
- Run the test suite to understand all features
- Customize configuration (queue sizes, history limits, etc.)

## Support

For issues or questions, refer to:
- Assignment specification: [assignment.md](assignment.md)
- Full documentation: [README.md](README.md)
- Code comments in source files
