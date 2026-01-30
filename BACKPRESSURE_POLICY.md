# Backpressure Policy Documentation

## 📋 Table of Contents
1. [What is Backpressure?](#what-is-backpressure)
2. [Why Do We Need It?](#why-do-we-need-it)
3. [Our Implementation](#our-implementation)
4. [Policy Comparison](#policy-comparison)
5. [Configuration](#configuration)
6. [Testing & Monitoring](#testing--monitoring)
7. [Best Practices](#best-practices)

---

## 🤔 What is Backpressure?

### Definition

**Backpressure** is what happens when a consumer (subscriber) cannot process messages as fast as they are being produced (published). The system must decide what to do with the "excess" messages that don't fit in the subscriber's queue.

### Real-World Analogy

Think of it like a highway during rush hour:

```
Cars arriving (Publishers) → Highway (System) → Exit ramp (Subscriber)
                                                      ↓
                                                 Only 1 car/second
```

If 10 cars per second try to exit, but the exit ramp can only handle 1 car per second, what happens to the other 9 cars?

**Options:**
1. **Buffer them** - Wait in a queue (but queue has limited size)
2. **Reroute them** - Send to different exit (drop oldest)
3. **Close the exit** - Stop accepting cars (disconnect subscriber)

---

## 🚨 Why Do We Need It?

### The Problem

Without backpressure handling, slow subscribers can:

1. **Cause memory exhaustion** - Queues grow unbounded → Server runs out of memory → Crash
2. **Affect other subscribers** - System resources depleted → Everyone suffers
3. **Create cascading failures** - One slow subscriber breaks the entire system

### Example Scenario

```
Publisher: Publishing 1000 messages/second
Subscriber A: Processing 1000 messages/second ✅ Keeping up
Subscriber B: Processing 10 messages/second ❌ Can't keep up

Without backpressure:
Time    | Subscriber B's Queue Size | System Memory
--------|---------------------------|---------------
1 sec   | 990 messages             | 1 MB
2 sec   | 1,980 messages           | 2 MB
10 sec  | 9,900 messages           | 10 MB
60 sec  | 59,400 messages          | 60 MB
...     | ...                      | CRASH!

With backpressure (drop oldest):
Time    | Subscriber B's Queue Size | System Memory
--------|---------------------------|---------------
1 sec   | 100 messages (max)       | Stable
2 sec   | 100 messages (max)       | Stable
10 sec  | 100 messages (max)       | Stable
60 sec  | 100 messages (max)       | Stable ✅
```

---

## ⚙️ Our Implementation

### Policy: Drop Oldest Message

**File:** `pubsub_manager.py` Lines 43-77

**How it works:**

```python
class Subscriber:
    MAX_QUEUE_SIZE = 100  # Configurable via config.MAX_SUBSCRIBER_QUEUE_SIZE

    async def enqueue_message(self, message: Message, topic: str) -> bool:
        try:
            # Step 1: Try to add message (non-blocking)
            self.message_queue.put_nowait({
                'topic': topic,
                'message': message,
                'ts': datetime.utcnow().isoformat() + "Z"
            })
            return True  # Success!

        except asyncio.QueueFull:
            # Step 2: Queue is full - Apply backpressure
            logger.warning(f"Queue full for subscriber {self.client_id}. Dropping oldest message.")

            try:
                # Step 3: Remove oldest message
                self.message_queue.get_nowait()

                # Step 4: Add new message
                self.message_queue.put_nowait({
                    'topic': topic,
                    'message': message,
                    'ts': datetime.utcnow().isoformat() + "Z"
                })

                return True  # Success (with drop)

            except Exception as e:
                logger.error(f"Error handling backpressure for {self.client_id}: {e}")
                return False
```

### Visual Flow

```
Normal Operation (Queue not full):
┌─────────────┐
│ New Message │
└──────┬──────┘
       │
       ▼
  Queue.put_nowait()
       │
       ▼
  ┌───────────┐
  │  Queue    │
  │  [msg]    │  ← Message added successfully
  │  [...]    │
  │  [empty]  │
  └───────────┘

Backpressure Triggered (Queue full):
┌─────────────┐
│ New Message │
└──────┬──────┘
       │
       ▼
  Queue.put_nowait()
       │
       ▼
    QueueFull!
       │
       ▼
  ┌───────────┐
  │  Queue    │
  │  [msg1]   │ ← OLDEST (will be dropped)
  │  [msg2]   │
  │  [...]    │
  │  [msg100] │
  └─────┬─────┘
        │
        ▼
   Queue.get_nowait()  ← Remove msg1
        │
        ▼
  ┌───────────┐
  │  Queue    │
  │  [msg2]   │
  │  [...]    │
  │  [msg100] │
  │  [empty]  │ ← Space created
  └─────┬─────┘
        │
        ▼
   Queue.put_nowait(new_msg)  ← Add new message
        │
        ▼
  ┌───────────┐
  │  Queue    │
  │  [msg2]   │
  │  [...]    │
  │  [msg100] │
  │  [msg101] │ ← New message added
  └───────────┘

Result: msg1 dropped, msg101 added
```

### Key Characteristics

1. **Bounded Queue** - Maximum 100 messages (configurable)
2. **Non-Blocking** - Publisher never waits for slow subscriber
3. **FIFO with Drop** - First In, First Out; oldest dropped on overflow
4. **Connection Maintained** - Subscriber stays connected
5. **Logged** - Every drop is logged with WARNING level
6. **Best-Effort** - System tries to deliver all messages, but guarantees recent delivery

---

## 📊 Policy Comparison

### Policy 1: Drop Oldest (Our Choice) ✅

**What happens:** When queue is full, remove oldest message and add new one

**Pros:**
- ✅ Subscriber stays connected
- ✅ Always gets most recent messages
- ✅ Good for real-time systems (latest data most important)
- ✅ No disruption to subscriber
- ✅ System remains stable

**Cons:**
- ❌ Subscriber may not realize messages were dropped
- ❌ Loses historical messages
- ❌ Can't guarantee message delivery

**Best For:**
- Real-time dashboards
- Live monitoring systems
- Stock price updates
- IoT sensor readings
- Any system where "latest" > "complete history"

**Example:**
```
Stock Price Updates:
$100 → $101 → $102 → ... → $150

If subscriber is slow:
- Old prices ($100-$149) dropped
- Always sees current price ($150) ✅
- Can still make trading decisions
```

---

### Policy 2: Drop Newest (Alternative)

**What happens:** When queue is full, reject new message, keep old ones

**Pros:**
- ✅ Guarantees historical order
- ✅ Subscriber eventually gets all "accepted" messages
- ✅ Good for audit trails

**Cons:**
- ❌ Subscriber falls further behind
- ❌ Never catches up
- ❌ May receive stale data

**Best For:**
- Log processing
- Audit trails
- Batch processing

---

### Policy 3: Disconnect with SLOW_CONSUMER Error

**What happens:** When queue is full, close connection and send error

**Pros:**
- ✅ Subscriber knows there's a problem
- ✅ Forces client to fix slow processing
- ✅ Prevents resource waste
- ✅ Clear failure signal

**Cons:**
- ❌ Disruptive (connection closed)
- ❌ Requires reconnection logic
- ❌ May lose messages during reconnect
- ❌ More aggressive

**Best For:**
- High-reliability systems
- When message loss is unacceptable
- When you want to force clients to optimize

**Implementation (Not Active):**
```python
except asyncio.QueueFull:
    # Send error to subscriber
    error_msg = ServerMessage(
        type="error",
        error=ErrorDetail(
            code=ErrorCode.SLOW_CONSUMER,
            message=f"Queue full. Closing connection."
        )
    )
    await subscriber.websocket.send_json(error_msg.model_dump(exclude_none=True))

    # Close connection
    await subscriber.websocket.close()

    # Remove from subscribers
    topic.remove_subscriber(client_id)

    return False
```

---

### Policy 4: Block Publisher (Not Recommended)

**What happens:** Publisher waits until subscriber has space

**Pros:**
- ✅ No message loss
- ✅ Complete delivery guarantee

**Cons:**
- ❌ Slow subscriber blocks ALL publishers
- ❌ Cascading slowdown
- ❌ One slow client breaks entire system
- ❌ Terrible performance

**Best For:**
- Almost never! (Use a proper queue system like RabbitMQ instead)

---

## 🎛️ Configuration

### Default Settings

```python
# In config.py
MAX_SUBSCRIBER_QUEUE_SIZE = 100  # messages per subscriber
```

### Custom Configuration

**Via Environment Variable:**
```bash
# Set custom queue size
export PUBSUB_MAX_QUEUE_SIZE=200

# Start server
python main.py
```

**Via Code:**
```python
# In config.py
class Config:
    MAX_SUBSCRIBER_QUEUE_SIZE = int(os.getenv("PUBSUB_MAX_QUEUE_SIZE", "100"))
```

### Choosing Queue Size

**Factors to consider:**

1. **Message Size** - Larger messages → smaller queue
2. **Publishing Rate** - Higher rate → larger queue
3. **Expected Subscriber Speed** - Slower subscribers → larger queue
4. **Available Memory** - More memory → larger queue

**Formula:**
```
Queue Size = (Publish Rate × Expected Delay) × Safety Factor

Example:
- Publish Rate: 100 messages/second
- Expected Delay: 1 second (subscriber 1 second behind)
- Safety Factor: 1.5 (50% buffer)

Queue Size = (100 × 1) × 1.5 = 150 messages
```

**Recommendations:**
- **Low throughput** (< 10 msg/sec): 50-100 messages
- **Medium throughput** (10-100 msg/sec): 100-200 messages
- **High throughput** (> 100 msg/sec): 200-500 messages

**Memory Calculation:**
```
Memory per Subscriber = Queue Size × Average Message Size

Example:
- Queue Size: 100
- Avg Message Size: 1 KB
- Memory: 100 × 1 KB = 100 KB per subscriber

With 1000 subscribers: 100 KB × 1000 = 100 MB
```

---

## 🧪 Testing & Monitoring

### How to Test Backpressure

**Using the example client:**
```bash
# Start server
python main.py

# Run backpressure test
python example_client.py
# Select option: 13. Test Backpressure Handling
```

**Manual Test:**
```python
import asyncio
import websockets
import json
import uuid

async def test_backpressure():
    # Create slow subscriber (doesn't read messages)
    async with websockets.connect("ws://localhost:8080/ws") as ws_sub:
        # Subscribe
        await ws_sub.send(json.dumps({
            "type": "subscribe",
            "topic": "test",
            "client_id": "slow-subscriber"
        }))
        await ws_sub.recv()  # Get ack

        # DON'T read messages (simulate slow consumer)

        # In another connection, publish 200 messages
        async with websockets.connect("ws://localhost:8080/ws") as ws_pub:
            for i in range(200):
                await ws_pub.send(json.dumps({
                    "type": "publish",
                    "topic": "test",
                    "message": {
                        "id": str(uuid.uuid4()),
                        "payload": {"seq": i}
                    }
                }))
                await ws_pub.recv()  # Get ack

        # Wait and check server logs
        await asyncio.sleep(5)

asyncio.run(test_backpressure())
```

**Expected Server Logs:**
```
WARNING:__main__:Queue full for subscriber slow-subscriber. Dropping oldest message.
WARNING:__main__:Queue full for subscriber slow-subscriber. Dropping oldest message.
WARNING:__main__:Queue full for subscriber slow-subscriber. Dropping oldest message.
...
```

### Monitoring Backpressure

**1. Server Logs**
```python
# In pubsub_manager.py
logger.warning(f"Queue full for subscriber {self.client_id}. Dropping oldest message.")
```

**Check logs:**
```bash
# If running server directly
python main.py | grep "Queue full"

# If using systemd
journalctl -u pubsub-service | grep "Queue full"
```

**2. Add Metrics (Recommended for Production)**

```python
# Add to pubsub_manager.py
from prometheus_client import Counter

backpressure_drops = Counter(
    'pubsub_backpressure_drops_total',
    'Total messages dropped due to backpressure',
    ['topic', 'client_id']
)

# In enqueue_message:
except asyncio.QueueFull:
    backpressure_drops.labels(topic=topic, client_id=self.client_id).inc()
    logger.warning(f"Queue full for subscriber {self.client_id}")
```

**3. Statistics Endpoint**

Add per-subscriber stats:
```python
@app.get("/subscriber-stats")
async def get_subscriber_stats():
    stats = {}
    for topic_name, topic in pubsub_manager.topics.items():
        for client_id, subscriber in topic.subscribers.items():
            stats[f"{topic_name}/{client_id}"] = {
                "queue_size": subscriber.message_queue.qsize(),
                "queue_max": subscriber.MAX_QUEUE_SIZE,
                "utilization": subscriber.message_queue.qsize() / subscriber.MAX_QUEUE_SIZE
            }
    return stats
```

---

## ✅ Best Practices

### For Subscribers

**1. Process Messages Quickly**
```python
async def fast_subscriber():
    async with websockets.connect(WS_URL) as ws:
        await ws.send(subscribe_msg)

        while True:
            message = await ws.recv()

            # BAD: Slow processing
            # time.sleep(5)  # Don't do this!
            # expensive_operation()

            # GOOD: Fast processing or async
            asyncio.create_task(process_async(message))
```

**2. Monitor Your Queue**

Request stats periodically to see if you're falling behind.

**3. Handle Errors Gracefully**
```python
try:
    while True:
        message = await ws.recv()
        process(message)
except Exception as e:
    logger.error(f"Error: {e}")
    # Reconnect logic
```

### For System Administrators

**1. Set Appropriate Queue Sizes**

Monitor backpressure frequency and adjust:
```bash
# If seeing many drops
export PUBSUB_MAX_QUEUE_SIZE=200

# If memory is concern
export PUBSUB_MAX_QUEUE_SIZE=50
```

**2. Monitor System Health**
```bash
# Check memory usage
free -h

# Check for backpressure
tail -f /var/log/pubsub.log | grep "Queue full"

# Check subscriber stats
curl http://localhost:8080/subscriber-stats
```

**3. Alert on Excessive Backpressure**
```
If backpressure_drops > 1000/minute:
  Alert: "Subscriber X is too slow"
  Action: Investigate subscriber performance
```

---

## 📈 Performance Impact

### Memory Usage

```
Per Subscriber Memory = Queue Size × Avg Message Size

Example with 100-message queue:
- Small messages (100 bytes): 10 KB
- Medium messages (1 KB): 100 KB
- Large messages (10 KB): 1 MB

With 1000 subscribers:
- Small: 10 MB
- Medium: 100 MB
- Large: 1 GB
```

### CPU Impact

**Minimal:**
- Queue operations: O(1)
- Drop oldest: O(1)
- No additional processing

**Overhead per message:**
- Normal: ~0.1ms
- With backpressure: ~0.2ms (one extra queue operation)

---

## 🎯 Summary

### Our Choice: Drop Oldest

**Why:**
1. **Stability** - System remains stable even with slow subscribers
2. **Simplicity** - Easy to understand and implement
3. **Real-time** - Perfect for systems where recent data matters
4. **No Disruption** - Subscribers stay connected

**Trade-offs:**
- Silent drops (logged server-side)
- No delivery guarantee
- May lose historical messages

**When to Use:**
- ✅ Real-time systems
- ✅ Monitoring dashboards
- ✅ Live updates
- ✅ IoT sensors
- ✅ Stock tickers

**When NOT to Use:**
- ❌ Financial transactions
- ❌ Audit logs
- ❌ Critical alerts
- ❌ Message ordering is critical

**Alternative:** If message delivery must be guaranteed, use a proper message queue system like RabbitMQ, Kafka, or Redis Streams instead of this in-memory pub/sub.

---

## 📚 Related Documentation

- [REQUIREMENTS_ANALYSIS.md](REQUIREMENTS_ANALYSIS.md) - Backpressure requirement explained
- [CODE_WALKTHROUGH.md](CODE_WALKTHROUGH.md) - Implementation details
- [BEGINNERS_README.md](BEGINNERS_README.md) - Simple explanation

---

**Policy Version:** 1.0
**Last Updated:** 2025-01-30
**Status:** Active ✅
