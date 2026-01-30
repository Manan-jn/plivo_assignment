# 📚 Beginner's Guide to the Pub/Sub System

## 🎯 What is This Project?

This is a **Publish-Subscribe (Pub/Sub) messaging system** - a way for different programs to talk to each other in real-time.

### Real-World Analogy

Think of it like **YouTube**:
- **Publishers** = YouTubers who upload videos
- **Topics** = YouTube channels
- **Subscribers** = People who subscribe to channels
- **Messages** = Videos uploaded to channels

When a YouTuber uploads a video, ALL subscribers to that channel get notified. That's exactly what this system does with data/messages!

---

## 🤔 Why Do We Need This?

Imagine you're building a food delivery app:

**Without Pub/Sub:**
```
Order Service ──► Directly calls ──► Restaurant Service
               └► Directly calls ──► Delivery Service
               └► Directly calls ──► Notification Service

Problems:
- If one service is slow, everything slows down
- Services are tightly coupled
- Hard to add new services
```

**With Pub/Sub:**
```
Order Service ──► Publishes "New Order" ──► Topic: "orders"
                                               ↓
                                    ┌──────────┼──────────┐
                                    ↓          ↓          ↓
                            Restaurant    Delivery   Notification
                             Service      Service     Service

Benefits:
- Services don't wait for each other
- Easy to add new subscribers
- Services don't need to know about each other
```

---

## 📖 Table of Contents

1. [Basic Concepts](#basic-concepts)
2. [How to Install](#how-to-install)
3. [Quick Start](#quick-start)
4. [Understanding the Code](#understanding-the-code)
5. [Step-by-Step Examples](#step-by-step-examples)
6. [Core Requirements Explained](#core-requirements-explained)
7. [Common Problems & Solutions](#common-problems--solutions)

---

## 💡 Basic Concepts

### What is a Topic?

A **topic** is like a chat room or a channel. Messages about similar things go to the same topic.

**Examples:**
- Topic "orders" → All order-related messages
- Topic "payments" → All payment-related messages
- Topic "notifications" → All notification messages

**In Code:**
```bash
# Create a topic named "orders"
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name":"orders"}'
```

### What is Publishing?

**Publishing** means sending a message to a topic.

**Real-World Analogy:** Posting a status update to Facebook

**In Code:**
```json
{
  "type": "publish",
  "topic": "orders",
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "payload": {
      "order_id": "ORD-123",
      "customer": "John Doe",
      "amount": 99.50
    }
  }
}
```

### What is Subscribing?

**Subscribing** means registering to receive messages from a topic.

**Real-World Analogy:** Following someone on Instagram - you see their posts

**In Code:**
```json
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "restaurant-service"
}
```

### What is a Message?

A **message** is the actual data being sent.

**Structure:**
```json
{
  "id": "unique-identifier-uuid",
  "payload": {
    // Your actual data goes here
    // Can be anything: numbers, text, objects
  }
}
```

---

## 🚀 How to Install

### Prerequisites

You need:
1. **Python 3.10 or higher** - The programming language
2. **pip** - Python package installer (comes with Python)

**Check if you have them:**
```bash
python --version  # Should show Python 3.10.x or higher
pip --version     # Should show pip version
```

### Installation Steps

**Step 1: Navigate to project folder**
```bash
cd "/Users/mananjain/Downloads/Plivo Assignment 2"
```

**Step 2: Install dependencies**
```bash
pip install -r requirements.txt
```

This installs:
- `fastapi` - Web framework
- `uvicorn` - Web server
- `websockets` - For real-time communication
- `pydantic` - For data validation

**Step 3: Verify installation**
```bash
python -c "import fastapi; print('FastAPI installed successfully!')"
```

---

## ⚡ Quick Start

### Starting the Server

**Method 1: Direct Python**
```bash
python main.py
```

**Method 2: Using the helper script**
```bash
./run.sh server
```

**Method 3: Using Docker**
```bash
docker build -t pubsub-system .
docker run -p 8080:8080 pubsub-system
```

**You should see:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
```

**✅ Server is ready when you see this message!**

### Your First Test

**Open a new terminal and run:**
```bash
# Check if server is running
curl http://localhost:8080/health
```

**Expected Response:**
```json
{
  "uptime_sec": 5,
  "topics": 0,
  "subscribers": 0
}
```

**🎉 Congratulations! Your server is working!**

---

## 📂 Understanding the Code

### File Structure

```
Plivo Assignment 2/
│
├── main.py                 ← 🎯 START HERE - Main application
├── pubsub_manager.py       ← Core business logic
├── models.py               ← Data structures
├── config.py               ← Settings
│
├── test_pubsub.py          ← Automated tests
├── example_client.py       ← Interactive demo
│
├── requirements.txt        ← Python dependencies
├── Dockerfile              ← Docker configuration
│
└── Documentation/
    ├── BEGINNERS_README.md     ← This file!
    ├── CODE_WALKTHROUGH.md     ← Detailed code explanation
    ├── TESTING_GUIDE.md        ← How to test
    └── REQUIREMENTS_ANALYSIS.md ← Requirements breakdown
```

### How Files Work Together

```
         User Request
              ↓
         main.py (FastAPI app)
          ↙        ↘
    REST API    WebSocket
         ↓          ↓
      pubsub_manager.py (Business Logic)
              ↓
         Manages Topics
              ↓
         Each Topic manages Subscribers
              ↓
         Each Subscriber has a Message Queue
```

---

## 📝 Step-by-Step Examples

### Example 1: Creating a Topic and Publishing Messages

**Goal:** Create an "orders" topic and send messages to it

**Step 1: Start the server**
```bash
python main.py
```

**Step 2: Create topic (in new terminal)**
```bash
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name":"orders"}'
```

**Response:**
```json
{
  "status": "created",
  "topic": "orders"
}
```

**Step 3: Verify topic was created**
```bash
curl http://localhost:8080/topics
```

**Response:**
```json
{
  "topics": [
    {
      "name": "orders",
      "subscribers": 0
    }
  ]
}
```

**Step 4: Connect via WebSocket and publish**

For this, you need a WebSocket client. Let's use Python:

```python
# save as test_publish.py
import asyncio
import json
import websockets
import uuid

async def publish_message():
    # Connect to WebSocket
    async with websockets.connect("ws://localhost:8080/ws") as websocket:
        # Create a message
        message = {
            "type": "publish",
            "topic": "orders",
            "message": {
                "id": str(uuid.uuid4()),  # Generate unique ID
                "payload": {
                    "order_id": "ORD-001",
                    "customer": "Alice",
                    "items": ["Pizza", "Coke"],
                    "total": 25.99
                }
            }
        }

        # Send message
        await websocket.send(json.dumps(message))
        print("Message sent!")

        # Receive acknowledgment
        response = await websocket.recv()
        print(f"Server response: {response}")

# Run it
asyncio.run(publish_message())
```

**Run it:**
```bash
python test_publish.py
```

**Output:**
```
Message sent!
Server response: {"type":"ack","topic":"orders","status":"ok","ts":"2025-01-30T10:00:00Z"}
```

### Example 2: Subscribing to Receive Messages

**Goal:** Subscribe to "orders" topic and receive messages in real-time

**Create subscriber script:**
```python
# save as test_subscribe.py
import asyncio
import json
import websockets

async def subscribe_to_orders():
    async with websockets.connect("ws://localhost:8080/ws") as websocket:
        # Subscribe to "orders" topic
        subscribe_msg = {
            "type": "subscribe",
            "topic": "orders",
            "client_id": "my-subscriber"
        }

        await websocket.send(json.dumps(subscribe_msg))
        print("Subscribed to 'orders' topic!")

        # Listen for messages
        while True:
            message = await websocket.recv()
            data = json.loads(message)

            if data['type'] == 'ack':
                print("✓ Subscription confirmed")

            elif data['type'] == 'event':
                print(f"\n📩 New order received:")
                print(f"   Order ID: {data['message']['payload']['order_id']}")
                print(f"   Customer: {data['message']['payload']['customer']}")
                print(f"   Total: ${data['message']['payload']['total']}")

asyncio.run(subscribe_to_orders())
```

**Run it (in separate terminal):**
```bash
python test_subscribe.py
```

**Now run the publisher (from Example 1) in another terminal:**
```bash
python test_publish.py
```

**Subscriber will show:**
```
Subscribed to 'orders' topic!
✓ Subscription confirmed

📩 New order received:
   Order ID: ORD-001
   Customer: Alice
   Total: $25.99
```

### Example 3: Multiple Subscribers (Fan-Out)

**Goal:** Show that ALL subscribers receive the same message

**Terminal 1: Start server**
```bash
python main.py
```

**Terminal 2: Subscriber 1**
```python
# Create subscriber1.py
import asyncio, json, websockets

async def main():
    async with websockets.connect("ws://localhost:8080/ws") as ws:
        await ws.send(json.dumps({
            "type": "subscribe",
            "topic": "orders",
            "client_id": "subscriber-1"
        }))
        print("[SUB-1] Subscribed!")

        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data['type'] == 'event':
                print(f"[SUB-1] Received: {data['message']['payload']}")

asyncio.run(main())
```

**Terminal 3: Subscriber 2**
```python
# Create subscriber2.py
import asyncio, json, websockets

async def main():
    async with websockets.connect("ws://localhost:8080/ws") as ws:
        await ws.send(json.dumps({
            "type": "subscribe",
            "topic": "orders",
            "client_id": "subscriber-2"
        }))
        print("[SUB-2] Subscribed!")

        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data['type'] == 'event':
                print(f"[SUB-2] Received: {data['message']['payload']}")

asyncio.run(main())
```

**Terminal 4: Publisher**
```bash
python test_publish.py
```

**Both subscribers will receive the message!**
```
[SUB-1] Received: {'order_id': 'ORD-001', 'customer': 'Alice', ...}
[SUB-2] Received: {'order_id': 'ORD-001', 'customer': 'Alice', ...}
```

---

## 🎓 Core Requirements Explained (Simple Terms)

### 1. Concurrency Safety

**What it means:** Multiple people can use the system at the same time without breaking it.

**Why it matters:**
Imagine a bank where 2 people try to withdraw from the same account at the exact same time. Without safety, both might succeed and the account goes negative!

**How we handle it:**
```python
# We use "locks" - like a turnstile at a subway
async with self.lock:  # Only 1 person can enter at a time
    # Do important stuff
    # Others wait their turn
```

**Real Example:**
```
Person A tries to create topic "orders" ────┐
                                             ├─► Lock ensures only 1 succeeds
Person B tries to create topic "orders" ────┘    The other gets "already exists"
```

### 2. Fan-Out

**What it means:** One message goes to ALL subscribers.

**Analogy:** Teacher announces homework → ALL students hear it

**In Action:**
```
Publisher: "New order #123"
     ↓
Topic: "orders"
     ↓
┌────┼────┬────┐
↓    ↓    ↓    ↓
S1   S2   S3   S4
All 4 subscribers get "New order #123"
```

**Code:**
```python
# We loop through ALL subscribers
for subscriber in topic.subscribers.values():
    subscriber.enqueue_message(message)  # Each gets a copy
```

### 3. Isolation

**What it means:** Topics don't interfere with each other.

**Analogy:** Different WhatsApp groups don't see each other's messages

**Example:**
```
Topic "orders"                Topic "payments"
- Subscriber A               - Subscriber C
- Subscriber B               - Subscriber D

Message to "orders" → Only A and B receive it
Message to "payments" → Only C and D receive it
```

**How it works:**
Each topic has its own:
- Subscriber list (completely separate)
- Message history (no sharing)
- Message queue (independent)

### 4. Backpressure

**What it means:** What happens when a subscriber is too slow?

**Analogy:** Your email inbox is full. New emails either:
- Delete old emails to make room (Drop Oldest) ← We do this
- Reject new emails (Disconnect) ← Alternative

**Visual:**
```
Subscriber Queue (max 100 messages):

Normal: [Msg1][Msg2][Msg3]...[Empty][Empty]  ← Space available

Full:   [Msg1][Msg2][Msg3]...[Msg99][Msg100] ← Full!

New message arrives! What to do?

Our solution (Drop Oldest):
[Msg2][Msg3][Msg4]...[Msg100][Msg101] ← Msg1 dropped
```

**Why Drop Oldest:**
- Subscriber stays connected
- Gets most recent (usually most important) messages
- Good for real-time systems

**Code:**
```python
try:
    queue.put_nowait(new_message)  # Try to add
except QueueFull:
    queue.get_nowait()  # Remove oldest
    queue.put_nowait(new_message)  # Add new one
```

### 5. Graceful Shutdown

**What it means:** When server stops, do it nicely.

**Analogy:** Store closing:
1. Lock door (no new customers) ✓
2. Let existing customers finish ✓
3. Guide everyone out politely ✓

**What we do:**
```python
# When server shuts down:
1. Send "server_shutdown" message to all subscribers
2. Wait 2 seconds for queues to drain
3. Log final statistics
4. Close cleanly
```

**Subscriber receives:**
```json
{
  "type": "info",
  "msg": "server_shutdown",
  "topic": "orders",
  "ts": "2025-01-30T10:00:00Z"
}
```

### 6. Message Replay (last_n)

**What it means:** New subscribers can see old messages.

**Analogy:** Joining a group chat and seeing the last 20 messages to understand context

**Usage:**
```json
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "late-subscriber",
  "last_n": 10  ← "Show me last 10 messages"
}
```

**What happens:**
```
1. Server sends ACK
2. Server sends last 10 historical messages (oldest first)
3. Server sends new messages as they arrive (real-time)
```

**How it works:**
```python
# We keep last 100 messages in a circular buffer
message_history = deque(maxlen=100)

# When someone publishes:
message_history.append(new_message)  # Auto-drops oldest if full

# When someone subscribes with last_n:
return message_history[-last_n:]  # Return last N messages
```

---

## 🐛 Common Problems & Solutions

### Problem 1: "Connection Refused"

**Error Message:**
```
ConnectionRefusedError: [Errno 61] Connection refused
```

**Cause:** Server is not running

**Solution:**
```bash
# Start the server
python main.py
```

**Check it's running:**
```bash
curl http://localhost:8080/health
```

---

### Problem 2: "Topic Not Found"

**Error Message:**
```json
{
  "type": "error",
  "error": {
    "code": "TOPIC_NOT_FOUND",
    "message": "Topic 'orders' does not exist"
  }
}
```

**Cause:** You tried to subscribe or publish to a topic that doesn't exist

**Solution:**
```bash
# Create the topic first
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name":"orders"}'

# Then subscribe/publish
```

---

### Problem 3: "Invalid UUID"

**Error Message:**
```json
{
  "type": "error",
  "error": {
    "code": "BAD_REQUEST",
    "message": "message.id must be a valid UUID"
  }
}
```

**Cause:** Message ID is not a proper UUID

**Bad:**
```json
{
  "message": {
    "id": "123",  ← Not a valid UUID
    "payload": {}
  }
}
```

**Good:**
```json
{
  "message": {
    "id": "550e8400-e29b-41d4-a716-446655440000",  ← Valid UUID
    "payload": {}
  }
}
```

**Generate Valid UUID in Python:**
```python
import uuid
message_id = str(uuid.uuid4())
print(message_id)
# Output: 550e8400-e29b-41d4-a716-446655440000
```

---

### Problem 4: "Port Already in Use"

**Error Message:**
```
OSError: [Errno 48] Address already in use
```

**Cause:** Another program is using port 8080

**Solution 1: Stop the other program**
```bash
# Find what's using port 8080
lsof -i :8080

# Kill it (replace PID with actual number)
kill -9 <PID>
```

**Solution 2: Use a different port**
```bash
# Set environment variable
export PUBSUB_PORT=9000

# Run server
python main.py
# Now it runs on port 9000
```

---

### Problem 5: WebSocket Closes Immediately

**Symptom:** Connection opens then closes right away

**Common Causes & Solutions:**

**Cause 1: Invalid JSON**
```python
# Bad
await websocket.send("not json")

# Good
await websocket.send(json.dumps({"type": "ping"}))
```

**Cause 2: Missing required fields**
```python
# Bad - missing client_id
{
  "type": "subscribe",
  "topic": "orders"
}

# Good
{
  "type": "subscribe",
  "topic": "orders",
  "client_id": "my-client"  ← Required!
}
```

**Debug Tip:**
Check server logs for error messages:
```bash
# Server logs show what went wrong
python main.py
# Look for ERROR or WARNING messages
```

---

## 🎯 Quick Reference

### Start Server
```bash
python main.py
```

### Create Topic
```bash
curl -X POST http://localhost:8080/topics \
  -H "Content-Type: application/json" \
  -d '{"name":"YOUR_TOPIC_NAME"}'
```

### List Topics
```bash
curl http://localhost:8080/topics
```

### Check Health
```bash
curl http://localhost:8080/health
```

### Subscribe (Python)
```python
import asyncio, json, websockets

async def subscribe():
    async with websockets.connect("ws://localhost:8080/ws") as ws:
        await ws.send(json.dumps({
            "type": "subscribe",
            "topic": "YOUR_TOPIC",
            "client_id": "YOUR_CLIENT_ID"
        }))

        while True:
            msg = await ws.recv()
            print(msg)

asyncio.run(subscribe())
```

### Publish (Python)
```python
import asyncio, json, websockets, uuid

async def publish():
    async with websockets.connect("ws://localhost:8080/ws") as ws:
        await ws.send(json.dumps({
            "type": "publish",
            "topic": "YOUR_TOPIC",
            "message": {
                "id": str(uuid.uuid4()),
                "payload": {"your": "data"}
            }
        }))

        response = await ws.recv()
        print(response)

asyncio.run(publish())
```

---

## 📚 Next Steps

Now that you understand the basics:

1. **Run the examples** in this guide
2. **Read [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md)** to understand how the code works
3. **Try [test_pubsub.py](test_pubsub.py)** - automated tests
4. **Use [example_client.py](example_client.py)** - interactive demo
5. **Import [PubSub_Postman_Collection.json](PubSub_Postman_Collection.json)** - test all endpoints

---

## 🆘 Getting Help

**If you're stuck:**
1. Check server logs for error messages
2. Read [Common Problems](#common-problems--solutions) section
3. Look at [TESTING_GUIDE.md](TESTING_GUIDE.md)
4. Check [REQUIREMENTS_ANALYSIS.md](REQUIREMENTS_ANALYSIS.md)

**File an issue with:**
- What you tried
- Error message (full text)
- Server logs
- Your code

---

## 🎉 Congratulations!

You now understand:
- ✅ What Pub/Sub is and why it's useful
- ✅ How to install and run the system
- ✅ How to create topics, publish, and subscribe
- ✅ What each requirement means
- ✅ How to fix common problems

**Happy coding! 🚀**
