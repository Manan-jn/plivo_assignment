# Visual Guide - System Diagrams

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │   REST       │  │  WebSocket   │  │  WebSocket   │              │
│  │   Client     │  │  Publisher   │  │  Subscriber  │              │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                 │                  │                       │
└─────────┼─────────────────┼──────────────────┼───────────────────────┘
          │ HTTP            │ WS               │ WS
          │                 │                  │
┌─────────┼─────────────────┼──────────────────┼───────────────────────┐
│         │                 │                  │                       │
│         ▼                 ▼                  ▼                       │
│  ┌─────────────────────────────────────────────────────┐           │
│  │          FastAPI Application (main.py)               │           │
│  ├─────────────────────────────────────────────────────┤           │
│  │                                                       │           │
│  │  ┌─────────────┐           ┌─────────────────────┐ │           │
│  │  │   REST      │           │    WebSocket        │ │           │
│  │  │   Routes    │           │    Handler          │ │           │
│  │  │             │           │    /ws              │ │           │
│  │  │ /topics     │           │                     │ │           │
│  │  │ /health     │           │  Message Router     │ │           │
│  │  │ /stats      │           │  - subscribe        │ │           │
│  │  │             │           │  - unsubscribe      │ │           │
│  │  │             │           │  - publish          │ │           │
│  │  │             │           │  - ping             │ │           │
│  │  └─────┬───────┘           └──────┬──────────────┘ │           │
│  │        │                          │                 │           │
│  │        └──────────┬───────────────┘                 │           │
│  │                   │                                 │           │
│  └───────────────────┼─────────────────────────────────┘           │
│                      │                                             │
│         APPLICATION LAYER                                          │
├──────────────────────┼──────────────────────────────────────────────┤
│                      │                                             │
│                      ▼                                             │
│            ┌─────────────────────┐                                │
│            │   PubSubManager     │                                │
│            │  (Singleton)        │                                │
│            ├─────────────────────┤                                │
│            │                     │                                │
│            │ topics: Dict        │                                │
│            │ lock: asyncio.Lock  │                                │
│            │ start_time: float   │                                │
│            │                     │                                │
│            └──────────┬──────────┘                                │
│                       │                                            │
│         BUSINESS LOGIC LAYER                                       │
├───────────────────────┼────────────────────────────────────────────┤
│                       │                                            │
│                       ▼                                            │
│         ┌─────────────────────────────┐                           │
│         │       Topics Dict           │                           │
│         ├─────────────────────────────┤                           │
│         │                             │                           │
│         │  "orders" ───► Topic        │                           │
│         │  "events" ───► Topic        │                           │
│         │  "notifs" ───► Topic        │                           │
│         │                             │                           │
│         └──────────┬──────────────────┘                           │
│                    │                                               │
│                    ▼                                               │
│         ┌─────────────────────┐                                   │
│         │      Topic          │                                   │
│         ├─────────────────────┤                                   │
│         │                     │                                   │
│         │ name: str           │                                   │
│         │ subscribers: Dict   │                                   │
│         │ message_history:    │                                   │
│         │   deque(maxlen=100) │                                   │
│         │ message_count: int  │                                   │
│         │ lock: asyncio.Lock  │                                   │
│         │                     │                                   │
│         └──────────┬──────────┘                                   │
│                    │                                               │
│                    ▼                                               │
│         ┌─────────────────────┐                                   │
│         │   Subscribers Dict  │                                   │
│         ├─────────────────────┤                                   │
│         │                     │                                   │
│         │ "client1" ► Sub     │                                   │
│         │ "client2" ► Sub     │                                   │
│         │ "client3" ► Sub     │                                   │
│         │                     │                                   │
│         └──────────┬──────────┘                                   │
│                    │                                               │
│         DATA LAYER │                                               │
├────────────────────┼───────────────────────────────────────────────┤
│                    │                                               │
│                    ▼                                               │
│         ┌─────────────────────┐                                   │
│         │    Subscriber       │                                   │
│         ├─────────────────────┤                                   │
│         │                     │                                   │
│         │ client_id: str      │                                   │
│         │ websocket: WS       │                                   │
│         │ message_queue:      │                                   │
│         │   Queue(maxlen=100) │                                   │
│         │ active: bool        │                                   │
│         │                     │                                   │
│         └─────────────────────┘                                   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Message Flow: Subscribe

```
┌─────────────┐                                    ┌─────────────────┐
│   Client    │                                    │  PubSubManager  │
└──────┬──────┘                                    └────────┬────────┘
       │                                                    │
       │  1. WebSocket Connect                             │
       ├──────────────────────────────────────────────────►│
       │                                                    │
       │  2. Subscribe Message                             │
       │  {                                                 │
       │    "type": "subscribe",                           │
       │    "topic": "orders",                             │
       │    "client_id": "sub1",                           │
       │    "last_n": 3                                    │
       │  }                                                 │
       ├──────────────────────────────────────────────────►│
       │                                                    │
       │                              3. Check topic exists │
       │                                 ┌──────────────────┤
       │                                 │ topics["orders"]? │
       │                                 └─────────────────►│
       │                                                    │
       │                              4. Create Subscriber  │
       │                                 ┌──────────────────┤
       │                                 │ Subscriber(...)   │
       │                                 └─────────────────►│
       │                                                    │
       │                              5. Add to topic       │
       │                                 ┌──────────────────┤
       │                                 │ topic.subscribers │
       │                                 │  ["sub1"] = sub  │
       │                                 └─────────────────►│
       │                                                    │
       │                              6. Get history (last_n)│
       │                                 ┌──────────────────┤
       │                                 │ history = [...]  │
       │                                 └─────────────────►│
       │                                                    │
       │  7. Send ACK                                       │
       │  {                                                 │
       │    "type": "ack",                                 │
       │    "status": "ok",                                │
       │    "topic": "orders"                              │
       │  }                                                 │
       │◄──────────────────────────────────────────────────┤
       │                                                    │
       │  8. Send Historical Messages (if last_n > 0)      │
       │  {                                                 │
       │    "type": "event",                               │
       │    "message": {...}                               │
       │  }                                                 │
       │◄──────────────────────────────────────────────────┤
       │◄──────────────────────────────────────────────────┤ (msg 2)
       │◄──────────────────────────────────────────────────┤ (msg 3)
       │                                                    │
       │                              9. Start background   │
       │                                 task to deliver    │
       │                                 future messages    │
       │                                 ┌──────────────────┤
       │                                 │ create_task()    │
       │                                 └─────────────────►│
       │                                                    │
       │  10. Background task runs                         │
       │      (waits for messages in queue)                │
       │                                                    │
```

---

## Message Flow: Publish

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│Publisher │  │  Topic   │  │  Sub1    │  │  Sub2    │  │  Sub3    │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │              │              │              │
     │ 1. Publish  │              │              │              │
     │  message    │              │              │              │
     ├────────────►│              │              │              │
     │             │              │              │              │
     │        2. Acquire lock    │              │              │
     │             │              │              │              │
     │        3. Add to history  │              │              │
     │             │              │              │              │
     │             ├─────┐        │              │              │
     │             │ msg │        │              │              │
     │             │ hist│        │              │              │
     │             │ory │        │              │              │
     │             │ [10 │        │              │              │
     │             │ 0]  │        │              │              │
     │             │     │        │              │              │
     │             └─────┘        │              │              │
     │             │              │              │              │
     │        4. Fan-out to all   │              │              │
     │           subscribers      │              │              │
     │             │              │              │              │
     │             ├──────────────┤              │              │
     │             │  enqueue_    │              │              │
     │             │  message()   │              │              │
     │             │              │              │              │
     │             │              ├───────┐      │              │
     │             │              │ Queue │      │              │
     │             │              │ [msg] │      │              │
     │             │              └───────┘      │              │
     │             │              │              │              │
     │             ├──────────────┼──────────────┤              │
     │             │              │  enqueue_    │              │
     │             │              │  message()   │              │
     │             │              │              │              │
     │             │              │        ┌─────┤              │
     │             │              │        │Queue│              │
     │             │              │        │[msg]│              │
     │             │              │        └─────┘              │
     │             │              │              │              │
     │             ├──────────────┼──────────────┼──────────────┤
     │             │              │              │  enqueue_    │
     │             │              │              │  message()   │
     │             │              │              │              │
     │             │              │              │        ┌─────┤
     │             │              │              │        │Queue│
     │             │              │              │        │[msg]│
     │             │              │              │        └─────┘
     │             │              │              │              │
     │        5. Release lock     │              │              │
     │             │              │              │              │
     │ 6. Send ACK │              │              │              │
     │◄────────────┤              │              │              │
     │             │              │              │              │
     │             │        7. Background tasks  │              │
     │             │           read queues       │              │
     │             │              │              │              │
     │             │              ├───────┐      │              │
     │             │              │ Read  │      │              │
     │             │              │ Queue │      │              │
     │             │              └───┬───┘      │              │
     │             │                  │          │              │
     │             │              8. Send event  │              │
     │             │                  │          │              │
     │             │              ┌───▼───┐      │              │
     │             │              │ Event │      │              │
     │             │              │  Msg  │      │              │
     │             │              └───────┘      │              │
     │             │              │              │              │
     │             │              │        ┌─────┤              │
     │             │              │        │Read │              │
     │             │              │        │Queue│              │
     │             │              │        └──┬──┘              │
     │             │              │           │                 │
     │             │              │       ┌───▼───┐             │
     │             │              │       │ Event │             │
     │             │              │       │  Msg  │             │
     │             │              │       └───────┘             │
     │             │              │              │              │
     │             │              │              │        ┌─────┤
     │             │              │              │        │Read │
     │             │              │              │        │Queue│
     │             │              │              │        └──┬──┘
     │             │              │              │           │
     │             │              │              │       ┌───▼───┐
     │             │              │              │       │ Event │
     │             │              │              │       │  Msg  │
     │             │              │              │       └───────┘
     │             │              │              │              │
```

---

## Data Structure Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                         PubSubManager                            │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                      topics: Dict                          │ │
│  │  ┌─────────────────────────────────────────────────────┐  │ │
│  │  │ Key: "orders" → Value: Topic                        │  │ │
│  │  │  ┌──────────────────────────────────────────────┐   │  │ │
│  │  │  │ name: "orders"                               │   │  │ │
│  │  │  │                                              │   │  │ │
│  │  │  │ subscribers: Dict                            │   │  │ │
│  │  │  │  ┌────────────────────────────────────────┐  │   │  │ │
│  │  │  │  │ "client1" → Subscriber                 │  │   │  │ │
│  │  │  │  │   ├─ client_id: "client1"             │  │   │  │ │
│  │  │  │  │   ├─ websocket: <WebSocket>           │  │   │  │ │
│  │  │  │  │   ├─ message_queue: Queue             │  │   │  │ │
│  │  │  │  │   │   [msg1, msg2, msg3, ...]         │  │   │  │ │
│  │  │  │  │   └─ active: True                     │  │   │  │ │
│  │  │  │  │                                        │  │   │  │ │
│  │  │  │  │ "client2" → Subscriber                 │  │   │  │ │
│  │  │  │  │   ├─ client_id: "client2"             │  │   │  │ │
│  │  │  │  │   ├─ websocket: <WebSocket>           │  │   │  │ │
│  │  │  │  │   ├─ message_queue: Queue             │  │   │  │ │
│  │  │  │  │   │   [msg1, msg2, ...]               │  │   │  │ │
│  │  │  │  │   └─ active: True                     │  │   │  │ │
│  │  │  │  └────────────────────────────────────────┘  │   │  │ │
│  │  │  │                                              │   │  │ │
│  │  │  │ message_history: deque(maxlen=100)          │   │  │ │
│  │  │  │  ┌────────────────────────────────────────┐ │   │  │ │
│  │  │  │  │ [0] {"message": {...}, "ts": "..."}   │ │   │  │ │
│  │  │  │  │ [1] {"message": {...}, "ts": "..."}   │ │   │  │ │
│  │  │  │  │ [2] {"message": {...}, "ts": "..."}   │ │   │  │ │
│  │  │  │  │ ...                                    │ │   │  │ │
│  │  │  │  │ [99] {"message": {...}, "ts": "..."}  │ │   │  │ │
│  │  │  │  └────────────────────────────────────────┘ │   │  │ │
│  │  │  │                                              │   │  │ │
│  │  │  │ message_count: 1523                         │   │  │ │
│  │  │  │ lock: asyncio.Lock                          │   │  │ │
│  │  │  └──────────────────────────────────────────────┘   │  │ │
│  │  │                                                     │  │ │
│  │  │ Key: "notifications" → Value: Topic                 │  │ │
│  │  │  [Similar structure...]                             │  │ │
│  │  └─────────────────────────────────────────────────────┘  │ │
│  │                                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  lock: asyncio.Lock (protects topics dict)                      │
│  start_time: 1706608000.0                                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Backpressure Flow

```
Normal Operation (Queue not full):
┌────────────┐     ┌──────────────────────────────┐
│ Publisher  │────►│ Topic.publish_message()      │
└────────────┘     │  ├─ Add to history           │
                   │  └─ Fan-out to subscribers   │
                   └────────┬─────────────────────┘
                            │
                            ▼
                   ┌────────────────────┐
                   │ Subscriber Queue   │
                   ├────────────────────┤
                   │ [Msg1]             │
                   │ [Msg2]             │
                   │ [Msg3]             │
                   │ [Empty slots...]   │ ← Space available
                   └────────────────────┘
                            │
                            ▼
                   ┌────────────────────┐
                   │ Background Task    │
                   │ Reads and sends    │
                   └────────────────────┘


Queue Full (Backpressure):
┌────────────┐     ┌──────────────────────────────┐
│ Publisher  │────►│ Topic.publish_message()      │
└────────────┘     │  ├─ Add to history           │
                   │  └─ Fan-out to subscribers   │
                   └────────┬─────────────────────┘
                            │
                            ▼
                   ┌────────────────────┐
                   │ Subscriber Queue   │
                   ├────────────────────┤
                   │ [Msg1] ◄─── OLDEST │ ← Drop this
                   │ [Msg2]             │
                   │ [Msg3]             │
                   │ ...                │
                   │ [Msg100]           │ ← Queue full!
                   └────────────────────┘
                            │
                            ▼ Try to add new message
                   ┌────────────────────┐
                   │ Queue.put_nowait() │
                   │   ↓                │
                   │ QueueFull!         │
                   │   ↓                │
                   │ Backpressure       │
                   │   ↓                │
                   │ Queue.get_nowait() │ ← Remove oldest
                   │   ↓                │
                   │ Queue.put_nowait() │ ← Add new
                   └────────────────────┘
                            │
                            ▼
                   ┌────────────────────┐
                   │ Updated Queue      │
                   ├────────────────────┤
                   │ [Msg2]             │ ← Msg1 dropped
                   │ [Msg3]             │
                   │ ...                │
                   │ [Msg100]           │
                   │ [Msg101] ◄─── NEW  │
                   └────────────────────┘
```

---

## REST API Request Flow

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ POST /topics {"name": "orders"}
       │
       ▼
┌──────────────────────┐
│  FastAPI Router      │
│  @app.post("/topics")│
└──────┬───────────────┘
       │
       │ 1. Pydantic validates request body
       │    CreateTopicRequest(**body)
       │
       ▼
┌──────────────────────┐
│ create_topic()       │
│ handler function     │
└──────┬───────────────┘
       │
       │ 2. Call PubSubManager
       │
       ▼
┌──────────────────────┐
│ PubSubManager        │
│  .create_topic()     │
└──────┬───────────────┘
       │
       │ 3. Acquire lock
       │
       ▼
┌──────────────────────┐
│ Check if exists      │
│ if name in topics:   │
│   return False       │
└──────┬───────────────┘
       │
       │ 4. Create Topic
       │
       ▼
┌──────────────────────┐
│ topics[name] =       │
│   Topic(name)        │
└──────┬───────────────┘
       │
       │ 5. Release lock
       │
       ▼
┌──────────────────────┐
│ Return True          │
└──────┬───────────────┘
       │
       │ 6. Build response
       │
       ▼
┌──────────────────────┐
│ CreateTopicResponse  │
│ {                    │
│   "status":"created",│
│   "topic": "orders"  │
│ }                    │
└──────┬───────────────┘
       │
       │ 7. HTTP 201 Created
       │
       ▼
┌──────────────────────┐
│   Client receives    │
│   response           │
└──────────────────────┘
```

---

## Concurrency: Lock Management

```
Timeline (3 concurrent operations):

T0: ┌──────────────────────────────────────────────────────────┐
    │ Coroutine 1: create_topic("orders")                      │
    │ ├─ Acquires PubSubManager.lock                           │
    │ ├─ Creates Topic("orders")                               │
    │ ├─ Adds to topics dict                                   │
    │ └─ Releases PubSubManager.lock                           │
    └──────────────────────────────────────────────────────────┘

T1:                 ┌──────────────────────────────────────────┐
                    │ Coroutine 2: subscribe("orders", ...)    │
                    │ ├─ Waits for PubSubManager.lock...       │
                    │ │                                         │

T2:                                 ┌────────────────────────────┐
                                    │ Coroutine 3: publish(...)  │
                                    │ ├─ Waits for lock...       │
                                    │ │                          │

T3: Lock released ──┐
                    │
                    └──► Coroutine 2 continues
                         ├─ Acquires PubSubManager.lock
                         ├─ Reads topics["orders"]
                         ├─ Releases PubSubManager.lock
                         ├─ Acquires Topic.lock
                         ├─ Adds subscriber
                         └─ Releases Topic.lock

T4:                                 Lock released ──┐
                                                    │
                                                    └──► Coroutine 3
                                                         ├─ Acquires lock
                                                         ├─ Publishes
                                                         └─ Releases

Key Points:
- Locks ensure atomic operations
- Minimal lock duration (fast release)
- Nested locks (PubSubManager → Topic → Queue)
- No deadlocks (consistent lock ordering)
```

---

## Error Handling Flow

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       │ Invalid message (e.g., bad UUID)
       │
       ▼
┌──────────────────────┐
│ WebSocket Handler    │
│ receive_json()       │
└──────┬───────────────┘
       │
       │ 1. Parse with Pydantic
       │    ClientMessage(**data)
       │
       ▼
┌──────────────────────┐
│ Message Router       │
│ if msg.type == ...   │
└──────┬───────────────┘
       │
       │ 2. Route to handler
       │
       ▼
┌──────────────────────┐
│ handle_publish()     │
└──────┬───────────────┘
       │
       │ 3. Validate UUID
       │    uuid.UUID(msg.id)
       │
       ▼
┌──────────────────────┐
│ ValueError raised!   │
└──────┬───────────────┘
       │
       │ 4. Catch exception
       │
       ▼
┌──────────────────────┐
│ send_error()         │
│  ├─ ErrorCode        │
│  ├─ Error message    │
│  └─ request_id       │
└──────┬───────────────┘
       │
       │ 5. Build error response
       │
       ▼
┌──────────────────────┐
│ ServerMessage        │
│ {                    │
│   "type": "error",   │
│   "error": {         │
│     "code": "...",   │
│     "message": "..." │
│   },                 │
│   "ts": "..."        │
│ }                    │
└──────┬───────────────┘
       │
       │ 6. Send via WebSocket
       │
       ▼
┌──────────────────────┐
│ Client receives      │
│ error message        │
└──────────────────────┘
```

---

These diagrams show the complete system architecture, message flows, data structures, and key processes like backpressure handling and error management!
