"""
Test script for the Pub/Sub system.
Demonstrates all WebSocket and REST API functionality.
"""

import asyncio
import json
import requests
import websockets
from datetime import datetime


BASE_URL = "http://localhost:8080"
WS_URL = "ws://localhost:8080/ws"


def print_section(title):
    """Print formatted section header"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}\n")


async def test_rest_apis():
    """Test all REST API endpoints"""
    print_section("Testing REST APIs")

    # 1. Create topics
    print("1. Creating topics...")
    topics = ["orders", "notifications", "events"]

    for topic in topics:
        response = requests.post(f"{BASE_URL}/topics", json={"name": topic})
        print(f"   Created topic '{topic}': {response.status_code} - {response.json()}")

    # Try creating duplicate (should fail with 409)
    response = requests.post(f"{BASE_URL}/topics", json={"name": "orders"})
    print(f"   Duplicate topic 'orders': {response.status_code} - {response.json()}")

    # 2. List topics
    print("\n2. Listing all topics...")
    response = requests.get(f"{BASE_URL}/topics")
    print(f"   Topics: {json.dumps(response.json(), indent=2)}")

    # 3. Health check
    print("\n3. Health check...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"   Health: {json.dumps(response.json(), indent=2)}")

    # 4. Statistics
    print("\n4. Statistics...")
    response = requests.get(f"{BASE_URL}/stats")
    print(f"   Stats: {json.dumps(response.json(), indent=2)}")


async def subscriber_client(client_id, topic, duration=10):
    """
    Subscriber client that listens for messages.

    Args:
        client_id: Unique subscriber ID
        topic: Topic to subscribe to
        duration: How long to listen (seconds)
    """
    async with websockets.connect(WS_URL) as websocket:
        # Subscribe to topic
        subscribe_msg = {
            "type": "subscribe",
            "topic": topic,
            "client_id": client_id,
            "last_n": 0,
            "request_id": f"sub-{client_id}"
        }
        await websocket.send(json.dumps(subscribe_msg))
        print(f"[{client_id}] Subscribed to '{topic}'")

        # Listen for messages
        try:
            end_time = asyncio.get_event_loop().time() + duration
            while asyncio.get_event_loop().time() < end_time:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    if data['type'] == 'event':
                        print(f"[{client_id}] Received event: {data['message']}")
                    elif data['type'] == 'ack':
                        print(f"[{client_id}] Subscription confirmed")
                except asyncio.TimeoutError:
                    continue

        except Exception as e:
            print(f"[{client_id}] Error: {e}")

        # Unsubscribe
        unsubscribe_msg = {
            "type": "unsubscribe",
            "topic": topic,
            "client_id": client_id,
            "request_id": f"unsub-{client_id}"
        }
        await websocket.send(json.dumps(unsubscribe_msg))
        print(f"[{client_id}] Unsubscribed from '{topic}'")


async def publisher_client(topic, num_messages=5):
    """
    Publisher client that sends messages.

    Args:
        topic: Topic to publish to
        num_messages: Number of messages to publish
    """
    async with websockets.connect(WS_URL) as websocket:
        print(f"[Publisher] Connected, publishing to '{topic}'")

        for i in range(num_messages):
            publish_msg = {
                "type": "publish",
                "topic": topic,
                "message": {
                    "id": f"550e8400-e29b-41d4-a716-44665544{i:04d}",
                    "payload": {
                        "message_num": i + 1,
                        "content": f"Test message {i + 1}",
                        "timestamp": datetime.utcnow().isoformat()
                    }
                },
                "request_id": f"pub-{i}"
            }
            await websocket.send(json.dumps(publish_msg))

            # Wait for acknowledgment
            response = await websocket.recv()
            data = json.loads(response)
            if data['type'] == 'ack':
                print(f"[Publisher] Message {i + 1} published successfully")

            await asyncio.sleep(0.5)  # Small delay between messages


async def test_pubsub_flow():
    """Test pub/sub message flow"""
    print_section("Testing Pub/Sub Message Flow")

    topic = "orders"

    # Start multiple subscribers
    subscribers = [
        asyncio.create_task(subscriber_client("subscriber-1", topic, duration=8)),
        asyncio.create_task(subscriber_client("subscriber-2", topic, duration=8)),
        asyncio.create_task(subscriber_client("subscriber-3", topic, duration=8))
    ]

    # Wait a bit for subscribers to connect
    await asyncio.sleep(1)

    # Start publisher
    publisher = asyncio.create_task(publisher_client(topic, num_messages=5))

    # Wait for all tasks to complete
    await publisher
    await asyncio.gather(*subscribers)


async def test_replay_functionality():
    """Test message replay (last_n parameter)"""
    print_section("Testing Message Replay Functionality")

    topic = "events"

    # Publish some messages first
    async with websockets.connect(WS_URL) as websocket:
        print("[Replay Test] Publishing 10 messages...")
        for i in range(10):
            publish_msg = {
                "type": "publish",
                "topic": topic,
                "message": {
                    "id": f"550e8400-e29b-41d4-a716-44665555{i:04d}",
                    "payload": {"seq": i + 1, "data": f"Message {i + 1}"}
                }
            }
            await websocket.send(json.dumps(publish_msg))
            await websocket.recv()  # Wait for ack

    # Now subscribe with last_n=5
    async with websockets.connect(WS_URL) as websocket:
        subscribe_msg = {
            "type": "subscribe",
            "topic": topic,
            "client_id": "replay-subscriber",
            "last_n": 5,
            "request_id": "replay-test"
        }
        await websocket.send(json.dumps(subscribe_msg))

        print("[Replay Test] Subscribed with last_n=5, receiving historical messages...")

        # Receive ack + 5 historical messages
        for _ in range(6):  # 1 ack + 5 events
            message = await websocket.recv()
            data = json.loads(message)
            if data['type'] == 'ack':
                print(f"[Replay Test] Subscription confirmed")
            elif data['type'] == 'event':
                print(f"[Replay Test] Historical message: {data['message']}")


async def test_ping_pong():
    """Test ping/pong functionality"""
    print_section("Testing Ping/Pong")

    async with websockets.connect(WS_URL) as websocket:
        ping_msg = {
            "type": "ping",
            "request_id": "ping-test-123"
        }
        await websocket.send(json.dumps(ping_msg))
        print("[Ping] Sent ping")

        response = await websocket.recv()
        data = json.loads(response)
        print(f"[Pong] Received: {data}")


async def test_error_handling():
    """Test error scenarios"""
    print_section("Testing Error Handling")

    async with websockets.connect(WS_URL) as websocket:
        # 1. Subscribe to non-existent topic
        print("1. Testing subscribe to non-existent topic...")
        subscribe_msg = {
            "type": "subscribe",
            "topic": "non-existent-topic",
            "client_id": "error-test",
            "request_id": "error-1"
        }
        await websocket.send(json.dumps(subscribe_msg))
        response = await websocket.recv()
        data = json.loads(response)
        print(f"   Response: {data}")

        # 2. Publish with invalid UUID
        print("\n2. Testing publish with invalid message ID...")
        publish_msg = {
            "type": "publish",
            "topic": "orders",
            "message": {
                "id": "invalid-uuid",
                "payload": {"test": "data"}
            },
            "request_id": "error-2"
        }
        await websocket.send(json.dumps(publish_msg))
        response = await websocket.recv()
        data = json.loads(response)
        print(f"   Response: {data}")

        # 3. Missing required fields
        print("\n3. Testing message with missing fields...")
        bad_msg = {
            "type": "subscribe",
            "request_id": "error-3"
            # Missing topic and client_id
        }
        await websocket.send(json.dumps(bad_msg))
        response = await websocket.recv()
        data = json.loads(response)
        print(f"   Response: {data}")


async def test_delete_topic():
    """Test topic deletion"""
    print_section("Testing Topic Deletion")

    # Subscribe to a topic
    async with websockets.connect(WS_URL) as websocket:
        subscribe_msg = {
            "type": "subscribe",
            "topic": "notifications",
            "client_id": "delete-test-subscriber",
            "request_id": "delete-test"
        }
        await websocket.send(json.dumps(subscribe_msg))
        await websocket.recv()  # Ack
        print("[Delete Test] Subscribed to 'notifications'")

        # Delete the topic via REST API
        print("[Delete Test] Deleting topic...")
        response = requests.delete(f"{BASE_URL}/topics/notifications")
        print(f"   Delete response: {response.status_code} - {response.json()}")

        # Should receive topic_deleted info message
        try:
            message = await asyncio.wait_for(websocket.recv(), timeout=2.0)
            data = json.loads(message)
            print(f"[Delete Test] Received notification: {data}")
        except asyncio.TimeoutError:
            print("[Delete Test] No notification received")


async def run_all_tests():
    """Run all tests in sequence"""
    print("\n" + "=" * 60)
    print("  PUB/SUB SYSTEM - COMPREHENSIVE TEST SUITE")
    print("=" * 60)

    # Test REST APIs
    await test_rest_apis()

    # Wait a bit
    await asyncio.sleep(1)

    # Test Pub/Sub flow
    await test_pubsub_flow()

    # Test replay
    await test_replay_functionality()

    # Test ping/pong
    await test_ping_pong()

    # Test error handling
    await test_error_handling()

    # Test topic deletion
    await test_delete_topic()

    # Final statistics
    print_section("Final System Statistics")
    response = requests.get(f"{BASE_URL}/stats")
    print(f"Stats: {json.dumps(response.json(), indent=2)}")

    response = requests.get(f"{BASE_URL}/health")
    print(f"\nHealth: {json.dumps(response.json(), indent=2)}")

    print("\n" + "=" * 60)
    print("  ALL TESTS COMPLETED")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    print("\nMake sure the server is running on localhost:8080")
    print("Run with: python main.py\n")

    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\nTests interrupted by user")
    except Exception as e:
        print(f"\nError running tests: {e}")
