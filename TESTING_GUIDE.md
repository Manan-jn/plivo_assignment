# Complete Testing Guide

## Table of Contents
1. [Using the Postman Collection](#using-the-postman-collection)
2. [WebSocket Testing Methods](#websocket-testing-methods)
3. [Testing Scenarios](#testing-scenarios)
4. [Common Test Patterns](#common-test-patterns)

---

## Using the Postman Collection

### 1. Import the Collection

**Option A: Import File**
1. Open Postman
2. Click "Import" button (top-left)
3. Select `PubSub_Postman_Collection.json`
4. Click "Import"

**Option B: Drag and Drop**
1. Drag `PubSub_Postman_Collection.json` into Postman window
2. Confirm import

### 2. Collection Structure

```
Pub/Sub System - Complete Test Suite
├── 1. Health & Observability
│   ├── Health Check
│   └── Get Statistics
├── 2. Topic Management
│   ├── Create Topic - orders
│   ├── Create Topic - notifications
│   ├── Create Topic - events
│   ├── Create Topic - demo
│   ├── Create Duplicate Topic (Error Test)
│   ├── List All Topics
│   ├── Delete Topic - demo
│   └── Delete Non-Existent Topic (Error Test)
├── 3. WebSocket Tests (Use WebSocket Client)
├── 4. WebSocket Examples
│   ├── Subscribe - Basic
│   ├── Subscribe - With Replay (last_n)
│   ├── Publish - Single Message
│   ├── Publish - Complex Payload
│   ├── Unsubscribe
│   └── Ping
├── 5. WebSocket Error Scenarios
│   ├── Subscribe to Non-Existent Topic
│   ├── Subscribe Without client_id
│   ├── Subscribe Without topic
│   ├── Publish With Invalid UUID
│   ├── Publish Without message
│   ├── Publish to Non-Existent Topic
│   └── Invalid Message Type
└── 6. Complete Workflow Test
    ├── Step 1 - Initial Health Check
    ├── Step 2 - Create Test Topic
    ├── Step 3 - Verify Topic Exists
    ├── Step 4 - Check Stats (No Messages Yet)
    ├── Step 5 - WebSocket Instructions
    ├── Step 6 - Check Stats After Messages
    ├── Step 7 - Delete Test Topic
    └── Step 8 - Final Health Check
```

### 3. Environment Variables

The collection uses these variables:
- `baseUrl`: `http://localhost:8080`
- `wsUrl`: `ws://localhost:8080/ws`

**To modify:**
1. Click collection name → Variables tab
2. Update values as needed
3. Click "Save"

---

## WebSocket Testing Methods

### Method 1: Postman WebSocket (Recommended for Quick Tests)

**Steps:**
1. In Postman, click "New" → "WebSocket Request"
2. Enter URL: `ws://localhost:8080/ws`
3. Click "Connect"
4. Copy message from collection (folder 4 or 5)
5. Paste in "Message" field
6. Click "Send"
7. View response in "Messages" panel

**Example:**
```json
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "postman-client"
}
```

### Method 2: Python Test Scripts (Recommended for Comprehensive Testing)

**Using test_pubsub.py:**
```bash
# Start server
python main.py

# In another terminal
python test_pubsub.py
```

This runs:
- All REST API tests
- Multi-subscriber pub/sub flow
- Message replay
- Error scenarios
- Topic deletion

**Using example_client.py:**
```bash
python example_client.py
```

Interactive menu for:
- Running as subscriber
- Running as publisher
- Testing ping/pong

### Method 3: wscat CLI (Recommended for Manual Testing)

**Install:**
```bash
npm install -g wscat
```

**Connect:**
```bash
wscat -c ws://localhost:8080/ws
```

**Example Session:**
```
Connected (press CTRL+C to quit)

> {"type": "subscribe", "topic": "orders", "client_id": "wscat-client"}
< {"type":"ack","topic":"orders","status":"ok","ts":"2025-01-30T10:00:00Z"}

> {"type": "publish", "topic": "orders", "message": {"id": "550e8400-e29b-41d4-a716-446655440000", "payload": {"test": "hello"}}}
< {"type":"ack","topic":"orders","status":"ok","ts":"2025-01-30T10:00:01Z"}
< {"type":"event","topic":"orders","message":{"id":"550e8400...","payload":{"test":"hello"}},"ts":"2025-01-30T10:00:01Z"}

> {"type": "ping"}
< {"type":"pong","ts":"2025-01-30T10:00:02Z"}
```

### Method 4: Browser WebSocket (For Custom Testing)

**JavaScript Console:**
```javascript
// Connect
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  console.log('Connected');

  // Subscribe
  ws.send(JSON.stringify({
    type: 'subscribe',
    topic: 'orders',
    client_id: 'browser-client'
  }));
};

ws.onmessage = (event) => {
  console.log('Received:', JSON.parse(event.data));
};

// Publish
ws.send(JSON.stringify({
  type: 'publish',
  topic: 'orders',
  message: {
    id: '550e8400-e29b-41d4-a716-446655440000',
    payload: { test: 'from browser' }
  }
}));

// Close
ws.close();
```

---

## Testing Scenarios

### Scenario 1: Basic Pub/Sub Flow

**Goal:** Verify message delivery from publisher to subscribers

**Steps:**

1. **Create topic** (Postman: "Create Topic - orders")
   ```
   POST /topics
   Body: {"name": "orders"}
   Expected: 201 Created
   ```

2. **Open 2 WebSocket connections** (wscat or Postman WebSocket)

3. **Subscribe both clients:**
   ```json
   // Client 1
   {"type": "subscribe", "topic": "orders", "client_id": "sub1"}

   // Client 2
   {"type": "subscribe", "topic": "orders", "client_id": "sub2"}
   ```

4. **Publish message from either client:**
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

5. **Verify both clients receive event:**
   ```json
   {
     "type": "event",
     "topic": "orders",
     "message": {
       "id": "550e8400-e29b-41d4-a716-446655440000",
       "payload": {"order_id": "ORD-123", "amount": 99.5}
     },
     "ts": "2025-01-30T10:00:00Z"
   }
   ```

6. **Check stats** (Postman: "Get Statistics")
   ```
   GET /stats
   Expected: orders topic shows 1 message, 2 subscribers
   ```

### Scenario 2: Message Replay (last_n)

**Goal:** Test historical message delivery

**Steps:**

1. **Create topic and publish 5 messages** (see Scenario 1)

2. **New subscriber with replay:**
   ```json
   {
     "type": "subscribe",
     "topic": "orders",
     "client_id": "replay-sub",
     "last_n": 3
   }
   ```

3. **Verify subscriber receives:**
   - 1 ack message
   - 3 historical event messages (oldest to newest)
   - Future messages as they're published

4. **Check stats:**
   - Total messages should reflect all published (5)
   - Subscriber count includes new subscriber

### Scenario 3: Error Handling

**Goal:** Verify proper error responses

**Test Cases:**

1. **Subscribe to non-existent topic:**
   ```json
   {"type": "subscribe", "topic": "fake", "client_id": "test"}
   ```
   Expected:
   ```json
   {
     "type": "error",
     "error": {"code": "TOPIC_NOT_FOUND", "message": "..."}
   }
   ```

2. **Publish with invalid UUID:**
   ```json
   {
     "type": "publish",
     "topic": "orders",
     "message": {"id": "not-a-uuid", "payload": {}}
   }
   ```
   Expected:
   ```json
   {
     "type": "error",
     "error": {"code": "BAD_REQUEST", "message": "message.id must be a valid UUID"}
   }
   ```

3. **Missing required fields:**
   ```json
   {"type": "subscribe", "topic": "orders"}
   ```
   Expected:
   ```json
   {
     "type": "error",
     "error": {"code": "BAD_REQUEST", "message": "client_id is required"}
   }
   ```

### Scenario 4: Topic Deletion

**Goal:** Verify subscribers are notified when topic is deleted

**Steps:**

1. **Subscribe to topic:**
   ```json
   {"type": "subscribe", "topic": "temp", "client_id": "test"}
   ```

2. **Delete topic via REST API** (Postman: "Delete Topic")
   ```
   DELETE /topics/temp
   Expected: 200 OK
   ```

3. **Verify WebSocket subscriber receives:**
   ```json
   {
     "type": "info",
     "topic": "temp",
     "msg": "topic_deleted",
     "ts": "2025-01-30T10:00:00Z"
   }
   ```

### Scenario 5: Multiple Topics Isolation

**Goal:** Verify topics don't interfere with each other

**Steps:**

1. **Create 2 topics:**
   ```
   POST /topics {"name": "topic1"}
   POST /topics {"name": "topic2"}
   ```

2. **Subscribe to each:**
   ```json
   // Connection 1
   {"type": "subscribe", "topic": "topic1", "client_id": "sub1"}

   // Connection 2
   {"type": "subscribe", "topic": "topic2", "client_id": "sub2"}
   ```

3. **Publish to topic1:**
   ```json
   {
     "type": "publish",
     "topic": "topic1",
     "message": {
       "id": "550e8400-e29b-41d4-a716-446655440000",
       "payload": {"data": "for topic1"}
     }
   }
   ```

4. **Verify:**
   - Connection 1 receives event ✓
   - Connection 2 does NOT receive event ✓

5. **Check stats:**
   - topic1: 1 message, 1 subscriber
   - topic2: 0 messages, 1 subscriber

### Scenario 6: Backpressure Testing

**Goal:** Verify slow consumer handling

**Note:** This requires custom script as it needs to trigger queue overflow (100+ messages)

**Python Script:**
```python
import asyncio
import json
import websockets

async def slow_subscriber():
    async with websockets.connect("ws://localhost:8080/ws") as ws:
        # Subscribe
        await ws.send(json.dumps({
            "type": "subscribe",
            "topic": "test",
            "client_id": "slow"
        }))

        # DON'T read messages (simulate slow consumer)
        await asyncio.sleep(60)

async def fast_publisher():
    async with websockets.connect("ws://localhost:8080/ws") as ws:
        # Publish 200 messages quickly
        for i in range(200):
            await ws.send(json.dumps({
                "type": "publish",
                "topic": "test",
                "message": {
                    "id": f"550e8400-e29b-41d4-a716-44665544{i:04d}",
                    "payload": {"seq": i}
                }
            }))
            await ws.recv()  # Get ack

# Run both concurrently
asyncio.gather(slow_subscriber(), fast_publisher())
```

**Expected:**
- Check server logs for "Queue full" warnings
- Oldest messages dropped (not delivered to slow subscriber)
- System remains stable

---

## Common Test Patterns

### Pattern 1: REST API Testing (Postman)

```
1. Run "Complete Workflow Test" folder
2. All requests run in sequence
3. Check each response status and body
4. Tests validate expected values
```

### Pattern 2: WebSocket Testing (wscat)

```bash
# Terminal 1: Subscriber
wscat -c ws://localhost:8080/ws
> {"type": "subscribe", "topic": "orders", "client_id": "sub1"}

# Terminal 2: Publisher
wscat -c ws://localhost:8080/ws
> {"type": "publish", "topic": "orders", "message": {"id": "550e8400-e29b-41d4-a716-446655440000", "payload": {"test": "data"}}}

# Terminal 1 shows received event
```

### Pattern 3: Automated Testing (Python)

```bash
# Run full test suite
python test_pubsub.py

# Run interactive client
python example_client.py
```

### Pattern 4: Load Testing

**Using Apache Bench for REST:**
```bash
# Create 1000 topics concurrently
ab -n 1000 -c 10 -p topic.json -T application/json http://localhost:8080/topics

# topic.json
{"name": "load-test"}
```

**Using Custom Script for WebSocket:**
```python
import asyncio
import websockets

async def client(client_id):
    async with websockets.connect("ws://localhost:8080/ws") as ws:
        # Subscribe
        await ws.send(...)
        # Publish
        for i in range(100):
            await ws.send(...)

# Run 100 concurrent clients
asyncio.gather(*[client(f"c{i}") for i in range(100)])
```

---

## Verification Checklist

### REST APIs ✓

- [ ] POST /topics creates topic (201)
- [ ] POST /topics duplicate returns 409
- [ ] GET /topics lists all topics
- [ ] DELETE /topics/{name} deletes topic (200)
- [ ] DELETE /topics/{name} non-existent returns 404
- [ ] GET /health returns uptime, topics, subscribers
- [ ] GET /stats returns per-topic stats

### WebSocket Subscribe ✓

- [ ] Subscribe with valid params returns ack
- [ ] Subscribe to non-existent topic returns error
- [ ] Subscribe without topic returns error
- [ ] Subscribe without client_id returns error
- [ ] Subscribe with last_n returns historical messages
- [ ] Multiple subscribers to same topic work

### WebSocket Publish ✓

- [ ] Publish with valid message returns ack
- [ ] Publish to non-existent topic returns error
- [ ] Publish without message returns error
- [ ] Publish with invalid UUID returns error
- [ ] Publish delivers to all subscribers (fan-out)
- [ ] Published message appears in stats

### WebSocket Other ✓

- [ ] Unsubscribe removes subscriber
- [ ] Ping returns pong
- [ ] Topic deletion notifies subscribers
- [ ] Invalid message type returns error

### System Behavior ✓

- [ ] Multiple concurrent clients supported
- [ ] Topic isolation (no cross-talk)
- [ ] Message ordering preserved per publisher
- [ ] Backpressure doesn't crash system
- [ ] Server remains stable under load

---

## Troubleshooting

### Issue: Connection Refused

**Cause:** Server not running

**Solution:**
```bash
python main.py
```

### Issue: Topic Not Found

**Cause:** Topic wasn't created

**Solution:**
```bash
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name": "your-topic"}'
```

### Issue: Invalid UUID Error

**Cause:** message.id is not a valid UUID

**Solution:** Use proper UUID:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000"
}
```

Generate UUIDs:
```python
import uuid
print(str(uuid.uuid4()))
```

### Issue: WebSocket Closes Immediately

**Cause:** Server error or invalid message

**Solution:**
- Check server logs
- Validate JSON format
- Ensure all required fields present

---

## Quick Reference

### Valid UUIDs for Testing
```
550e8400-e29b-41d4-a716-446655440000
650e8400-e29b-41d4-a716-446655440001
750e8400-e29b-41d4-a716-446655440002
850e8400-e29b-41d4-a716-446655440003
```

### Common Topics for Testing
```
orders
notifications
events
demo
test
```

### Error Codes
```
BAD_REQUEST       - Invalid message or missing fields
TOPIC_NOT_FOUND   - Topic doesn't exist
SLOW_CONSUMER     - Queue overflow (backpressure)
INTERNAL          - Server error
```

---

## Running the Complete Test Suite

### Option 1: Postman Collection
1. Import collection
2. Run "Complete Workflow Test" folder
3. Check all tests pass

### Option 2: Python Script
```bash
python test_pubsub.py
```

### Option 3: Manual Testing
1. Create topics (Postman)
2. Open multiple wscat connections
3. Subscribe with different client_ids
4. Publish messages
5. Verify all receive events
6. Check stats endpoint
7. Delete topics

---

## Summary

This guide covers:
- ✅ Importing and using Postman collection
- ✅ 4 methods for WebSocket testing
- ✅ 6 comprehensive test scenarios
- ✅ Common test patterns
- ✅ Verification checklist
- ✅ Troubleshooting guide

For automated testing, use `test_pubsub.py`. For manual exploration, use Postman + wscat.
