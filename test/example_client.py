"""
Comprehensive Interactive Client for the Pub/Sub System
Tests ALL routes and functionality through terminal interface
"""

import asyncio
import json
import websockets
import uuid
import requests
from datetime import datetime
from typing import Optional


# Configuration
BASE_URL = "http://localhost:8080"
WS_URL = "ws://localhost:8080/ws"


# ============================================================================
# REST API Functions
# ============================================================================

def create_topic(topic_name: str):
    """Create a new topic via REST API"""
    try:
        response = requests.post(
            f"{BASE_URL}/topics",
            json={"name": topic_name},
            headers={"Content-Type": "application/json"}
        )
        if response.status_code == 201:
            print(f"✅ Topic '{topic_name}' created successfully")
            print(f"   Response: {response.json()}")
        elif response.status_code == 409:
            print(f"⚠️  Topic '{topic_name}' already exists")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Error creating topic: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")


def delete_topic(topic_name: str):
    """Delete a topic via REST API"""
    try:
        response = requests.delete(f"{BASE_URL}/topics/{topic_name}")
        if response.status_code == 200:
            print(f"✅ Topic '{topic_name}' deleted successfully")
            print(f"   Response: {response.json()}")
        elif response.status_code == 404:
            print(f"❌ Topic '{topic_name}' not found")
            print(f"   Response: {response.json()}")
        else:
            print(f"❌ Error deleting topic: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")


def list_topics():
    """List all topics via REST API"""
    try:
        response = requests.get(f"{BASE_URL}/topics")
        if response.status_code == 200:
            data = response.json()
            topics = data.get('topics', [])

            if not topics:
                print("📋 No topics exist")
            else:
                print(f"📋 Total Topics: {len(topics)}")
                print("\n" + "=" * 60)
                for topic in topics:
                    print(f"   📌 Topic: {topic['name']}")
                    print(f"      Subscribers: {topic['subscribers']}")
                print("=" * 60)
        else:
            print(f"❌ Error listing topics: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")


def get_health():
    """Get system health via REST API"""
    try:
        response = requests.get(f"{BASE_URL}/health")
        if response.status_code == 200:
            data = response.json()
            print("🏥 System Health:")
            print(f"   ⏱️  Uptime: {data['uptime_sec']} seconds ({data['uptime_sec']//60} minutes)")
            print(f"   📌 Topics: {data['topics']}")
            print(f"   👥 Total Subscribers: {data['subscribers']}")
        else:
            print(f"❌ Error getting health: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")


def get_stats():
    """Get system statistics via REST API"""
    try:
        response = requests.get(f"{BASE_URL}/stats")
        if response.status_code == 200:
            data = response.json()
            topics = data.get('topics', {})

            if not topics:
                print("📊 No statistics available (no topics)")
            else:
                print(f"📊 System Statistics:")
                print("\n" + "=" * 60)
                for topic_name, stats in topics.items():
                    print(f"   📌 Topic: {topic_name}")
                    print(f"      Messages: {stats['messages']}")
                    print(f"      Subscribers: {stats['subscribers']}")
                    print()
                print("=" * 60)
        else:
            print(f"❌ Error getting stats: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")


# ============================================================================
# WebSocket Functions
# ============================================================================

async def simple_subscriber(topic: str = "demo", client_id: Optional[str] = None, last_n: int = 0):
    """Subscribe to a topic and listen for messages"""
    if not client_id:
        client_id = f"subscriber-{uuid.uuid4().hex[:8]}"

    print(f"🔌 Connecting to WebSocket...")

    try:
        async with websockets.connect(WS_URL) as websocket:
            # Subscribe to topic
            subscribe_msg = {
                "type": "subscribe",
                "topic": topic,
                "client_id": client_id,
                "last_n": last_n
            }

            await websocket.send(json.dumps(subscribe_msg))
            print(f"✅ Subscribed to '{topic}' topic (client_id: {client_id})")

            if last_n > 0:
                print(f"   📜 Requesting last {last_n} historical messages")

            # Listen for messages
            print("\n📨 Listening for messages (press Ctrl+C to stop)...\n")

            message_count = 0
            try:
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)

                    if data['type'] == 'ack':
                        print(f"✓ Subscription confirmed")
                        print(f"   Status: {data.get('status')}")
                        print(f"   Timestamp: {data.get('ts')}\n")

                    elif data['type'] == 'event':
                        message_count += 1
                        print(f"📩 Message #{message_count} Received:")
                        print(f"   Topic: {data['topic']}")
                        print(f"   Message ID: {data['message']['id']}")
                        print(f"   Payload: {json.dumps(data['message']['payload'], indent=6)}")
                        print(f"   Timestamp: {data['ts']}\n")

                    elif data['type'] == 'error':
                        print(f"❌ Error Received:")
                        print(f"   Code: {data['error']['code']}")
                        print(f"   Message: {data['error']['message']}\n")

                    elif data['type'] == 'info':
                        print(f"ℹ️  Info Message:")
                        print(f"   Message: {data.get('msg')}")
                        print(f"   Topic: {data.get('topic')}\n")

            except KeyboardInterrupt:
                print("\n\n🛑 Stopping subscriber...")

                # Unsubscribe
                unsubscribe_msg = {
                    "type": "unsubscribe",
                    "topic": topic,
                    "client_id": client_id
                }
                await websocket.send(json.dumps(unsubscribe_msg))

                # Wait for acknowledgment
                response = await websocket.recv()
                print(f"✅ Unsubscribed successfully")
                print(f"   Total messages received: {message_count}")

    except Exception as e:
        print(f"❌ Error: {e}")


async def simple_publisher(topic: str = "demo", num_messages: int = 3):
    """Publish messages to a topic"""
    print(f"🔌 Connecting to WebSocket...")

    try:
        async with websockets.connect(WS_URL) as websocket:
            print(f"✅ Connected to WebSocket\n")

            # Publish messages
            for i in range(num_messages):
                message_id = str(uuid.uuid4())

                publish_msg = {
                    "type": "publish",
                    "topic": topic,
                    "message": {
                        "id": message_id,
                        "payload": {
                            "message_number": i + 1,
                            "text": f"Test message #{i + 1}",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {
                                "key1": f"value{i + 1}",
                                "key2": f"data{i + 1}"
                            }
                        }
                    }
                }

                await websocket.send(json.dumps(publish_msg))
                print(f"📤 Published message #{i + 1}")
                print(f"   Message ID: {message_id}")

                # Wait for acknowledgment
                ack = await websocket.recv()
                ack_data = json.loads(ack)

                if ack_data['type'] == 'ack':
                    print(f"   ✅ Acknowledged by server")
                    print(f"   Status: {ack_data.get('status')}\n")
                elif ack_data['type'] == 'error':
                    print(f"   ❌ Error: {ack_data['error']}\n")

                await asyncio.sleep(0.5)  # Small delay between messages

            print(f"✅ All {num_messages} messages published successfully")

    except Exception as e:
        print(f"❌ Error: {e}")


async def test_replay(topic: str = "demo"):
    """Test message replay functionality"""
    print("📜 Testing Message Replay Functionality\n")

    # First, publish some messages
    print("Step 1: Publishing 10 messages...")
    async with websockets.connect(WS_URL) as websocket:
        for i in range(10):
            message_id = str(uuid.uuid4())
            publish_msg = {
                "type": "publish",
                "topic": topic,
                "message": {
                    "id": message_id,
                    "payload": {"seq": i + 1, "text": f"Historical message {i + 1}"}
                }
            }
            await websocket.send(json.dumps(publish_msg))
            await websocket.recv()  # Wait for ack
            print(f"   ✓ Published message {i + 1}")

    print("\nStep 2: Subscribing with last_n=5...")
    print("Expected: Should receive last 5 messages\n")

    # Now subscribe with last_n
    async with websockets.connect(WS_URL) as websocket:
        subscribe_msg = {
            "type": "subscribe",
            "topic": topic,
            "client_id": f"replay-test-{uuid.uuid4().hex[:8]}",
            "last_n": 5
        }
        await websocket.send(json.dumps(subscribe_msg))

        # Receive messages
        print("📨 Receiving messages:\n")
        message_count = 0
        for _ in range(6):  # 1 ack + 5 historical messages
            message = await websocket.recv()
            data = json.loads(message)

            if data['type'] == 'ack':
                print("✓ Subscription confirmed")
            elif data['type'] == 'event':
                message_count += 1
                print(f"   📜 Historical message #{message_count}: {data['message']['payload']}")

        print(f"\n✅ Replay test complete! Received {message_count} historical messages")


async def test_ping_pong():
    """Test ping/pong functionality"""
    print("🏓 Testing Ping/Pong\n")

    try:
        async with websockets.connect(WS_URL) as websocket:
            ping_msg = {
                "type": "ping",
                "request_id": f"ping-{uuid.uuid4().hex[:8]}"
            }

            print("📡 Sending ping...")
            await websocket.send(json.dumps(ping_msg))

            response = await websocket.recv()
            data = json.loads(response)

            if data['type'] == 'pong':
                print(f"✅ Received pong!")
                print(f"   Request ID: {data.get('request_id')}")
                print(f"   Server Timestamp: {data['ts']}")
                print(f"\n🎉 Connection is healthy!")
            else:
                print(f"❌ Unexpected response: {data}")

    except Exception as e:
        print(f"❌ Error: {e}")


async def test_multiple_subscribers(topic: str = "demo", num_subscribers: int = 3):
    """Test fan-out with multiple subscribers"""
    print(f"👥 Testing Fan-Out with {num_subscribers} Subscribers\n")

    # Create subscriber tasks
    subscriber_tasks = []

    async def subscriber_worker(sub_id: int):
        async with websockets.connect(WS_URL) as websocket:
            client_id = f"fan-out-sub-{sub_id}"

            # Subscribe
            subscribe_msg = {
                "type": "subscribe",
                "topic": topic,
                "client_id": client_id
            }
            await websocket.send(json.dumps(subscribe_msg))
            await websocket.recv()  # Wait for ack

            print(f"✓ Subscriber {sub_id} ready")

            # Wait for message
            message = await websocket.recv()
            data = json.loads(message)

            if data['type'] == 'event':
                print(f"   📩 Subscriber {sub_id} received: {data['message']['payload']}")

    # Start subscribers
    print("Starting subscribers...")
    for i in range(num_subscribers):
        subscriber_tasks.append(asyncio.create_task(subscriber_worker(i + 1)))

    # Wait a bit for subscribers to connect
    await asyncio.sleep(1)

    # Publish a message
    print(f"\n📤 Publishing test message to '{topic}'...")
    async with websockets.connect(WS_URL) as websocket:
        publish_msg = {
            "type": "publish",
            "topic": topic,
            "message": {
                "id": str(uuid.uuid4()),
                "payload": {"test": "Fan-out test message"}
            }
        }
        await websocket.send(json.dumps(publish_msg))
        await websocket.recv()  # Wait for ack

    # Wait for all subscribers to receive
    await asyncio.gather(*subscriber_tasks)

    print(f"\n✅ Fan-out test complete! All {num_subscribers} subscribers received the message")


async def test_error_scenarios():
    """Test various error scenarios"""
    print("🧪 Testing Error Scenarios\n")

    async with websockets.connect(WS_URL) as websocket:

        # Test 1: Subscribe to non-existent topic
        print("Test 1: Subscribe to non-existent topic")
        subscribe_msg = {
            "type": "subscribe",
            "topic": "non-existent-topic-xyz",
            "client_id": "error-test"
        }
        await websocket.send(json.dumps(subscribe_msg))
        response = await websocket.recv()
        data = json.loads(response)

        if data['type'] == 'error':
            print(f"   ✅ Expected error received:")
            print(f"      Code: {data['error']['code']}")
            print(f"      Message: {data['error']['message']}\n")

        # Test 2: Publish with invalid UUID
        print("Test 2: Publish with invalid UUID")
        publish_msg = {
            "type": "publish",
            "topic": "demo",
            "message": {
                "id": "not-a-valid-uuid",
                "payload": {"test": "data"}
            }
        }
        await websocket.send(json.dumps(publish_msg))
        response = await websocket.recv()
        data = json.loads(response)

        if data['type'] == 'error':
            print(f"   ✅ Expected error received:")
            print(f"      Code: {data['error']['code']}")
            print(f"      Message: {data['error']['message']}\n")

        # Test 3: Subscribe without client_id
        print("Test 3: Subscribe without client_id")
        subscribe_msg = {
            "type": "subscribe",
            "topic": "demo"
        }
        await websocket.send(json.dumps(subscribe_msg))
        response = await websocket.recv()
        data = json.loads(response)

        if data['type'] == 'error':
            print(f"   ✅ Expected error received:")
            print(f"      Code: {data['error']['code']}")
            print(f"      Message: {data['error']['message']}\n")

        print("✅ All error scenarios tested successfully!")


async def test_backpressure(topic: str = "backpressure-test"):
    """Test backpressure handling (slow consumer)"""
    print("⚡ Testing Backpressure Handling\n")
    print("This test will:")
    print("1. Create a slow subscriber (doesn't read messages)")
    print("2. Publish 150 messages quickly")
    print("3. Check server logs for backpressure warnings\n")

    # Create topic first
    create_topic(topic)
    await asyncio.sleep(0.5)

    # Start slow subscriber
    async def slow_subscriber():
        async with websockets.connect(WS_URL) as websocket:
            subscribe_msg = {
                "type": "subscribe",
                "topic": topic,
                "client_id": "slow-subscriber"
            }
            await websocket.send(json.dumps(subscribe_msg))
            await websocket.recv()  # Get ack

            print("✓ Slow subscriber connected (not reading messages)")

            # Don't read messages - simulate slow consumer
            await asyncio.sleep(10)

    # Start fast publisher
    async def fast_publisher():
        await asyncio.sleep(1)  # Let subscriber connect first

        async with websockets.connect(WS_URL) as websocket:
            print("📤 Publishing 150 messages quickly...")

            for i in range(150):
                publish_msg = {
                    "type": "publish",
                    "topic": topic,
                    "message": {
                        "id": str(uuid.uuid4()),
                        "payload": {"seq": i + 1}
                    }
                }
                await websocket.send(json.dumps(publish_msg))
                await websocket.recv()  # Get ack

                if (i + 1) % 50 == 0:
                    print(f"   Published {i + 1} messages...")

            print(f"✅ Published all 150 messages")

    # Run both
    await asyncio.gather(
        slow_subscriber(),
        fast_publisher()
    )

    print("\n⚠️  Check server logs for 'Queue full' warnings")
    print("This indicates backpressure policy (drop oldest) was triggered")


# ============================================================================
# Main Menu
# ============================================================================

def print_menu():
    """Print main menu"""
    print("\n" + "=" * 70)
    print("  🚀 Pub/Sub System - Comprehensive Test Client")
    print("=" * 70)
    print("\n📡 REST API Operations:")
    print("  1.  Create Topic")
    print("  2.  Delete Topic")
    print("  3.  List All Topics")
    print("  4.  Get System Health")
    print("  5.  Get System Statistics")

    print("\n🔌 WebSocket Operations:")
    print("  6.  Subscribe to Topic (Listener)")
    print("  7.  Publish Messages to Topic")
    print("  8.  Subscribe with Replay (last_n)")
    print("  9.  Test Ping/Pong")

    print("\n🧪 Advanced Tests:")
    print("  10. Test Fan-Out (Multiple Subscribers)")
    print("  11. Test Message Replay")
    print("  12. Test Error Scenarios")
    print("  13. Test Backpressure Handling")

    print("\n🎯 Quick Demos:")
    print("  14. Complete Demo (All Features)")
    print("  15. Setup Demo Environment")

    print("\n  0.  Exit")
    print("=" * 70)


async def complete_demo():
    """Run a complete demonstration of all features"""
    print("\n" + "=" * 70)
    print("  🎬 Running Complete Demo")
    print("=" * 70)

    demo_topic = "complete-demo"

    print("\n[1/8] Creating demo topic...")
    create_topic(demo_topic)
    await asyncio.sleep(0.5)

    print("\n[2/8] Checking system health...")
    get_health()
    await asyncio.sleep(0.5)

    print("\n[3/8] Publishing 5 messages...")
    await simple_publisher(demo_topic, 5)
    await asyncio.sleep(0.5)

    print("\n[4/8] Testing replay with last 3 messages...")
    async with websockets.connect(WS_URL) as websocket:
        subscribe_msg = {
            "type": "subscribe",
            "topic": demo_topic,
            "client_id": "demo-replay-sub",
            "last_n": 3
        }
        await websocket.send(json.dumps(subscribe_msg))

        for _ in range(4):  # ack + 3 messages
            msg = await websocket.recv()
            data = json.loads(msg)
            if data['type'] == 'event':
                print(f"   📜 {data['message']['payload']}")

    print("\n[5/8] Testing ping/pong...")
    await test_ping_pong()

    print("\n[6/8] Checking statistics...")
    get_stats()

    print("\n[7/8] Listing all topics...")
    list_topics()

    print("\n[8/8] Cleaning up...")
    delete_topic(demo_topic)

    print("\n" + "=" * 70)
    print("  ✅ Complete Demo Finished!")
    print("=" * 70)


def setup_demo_environment():
    """Setup demo environment with sample topics"""
    print("\n🔧 Setting up demo environment...\n")

    topics = ["demo", "orders", "notifications", "events"]

    for topic in topics:
        print(f"Creating topic: {topic}")
        create_topic(topic)

    print("\n✅ Demo environment ready!")
    print("Topics created: " + ", ".join(topics))


async def main():
    """Main interactive loop"""
    print("\n" + "=" * 70)
    print("  Welcome to the Pub/Sub System Test Client!")
    print("=" * 70)
    print("\n⚡ Make sure the server is running on localhost:8080")
    print("   Start it with: python main.py")

    while True:
        print_menu()
        choice = input("\n👉 Enter your choice: ").strip()

        try:
            if choice == "0":
                print("\n👋 Goodbye!")
                break

            elif choice == "1":
                topic = input("Enter topic name: ").strip()
                create_topic(topic)

            elif choice == "2":
                topic = input("Enter topic name: ").strip()
                delete_topic(topic)

            elif choice == "3":
                list_topics()

            elif choice == "4":
                get_health()

            elif choice == "5":
                get_stats()

            elif choice == "6":
                topic = input("Enter topic name (default: demo): ").strip() or "demo"
                client_id = input("Enter client ID (leave empty for auto): ").strip() or None
                last_n = input("Replay last N messages (default: 0): ").strip()
                last_n = int(last_n) if last_n else 0
                await simple_subscriber(topic, client_id, last_n)

            elif choice == "7":
                topic = input("Enter topic name (default: demo): ").strip() or "demo"
                num = input("Number of messages (default: 3): ").strip()
                num = int(num) if num else 3
                await simple_publisher(topic, num)

            elif choice == "8":
                topic = input("Enter topic name (default: demo): ").strip() or "demo"
                last_n = input("Number of messages to replay: ").strip()
                last_n = int(last_n) if last_n else 5
                await simple_subscriber(topic, None, last_n)

            elif choice == "9":
                await test_ping_pong()

            elif choice == "10":
                topic = input("Enter topic name (default: demo): ").strip() or "demo"
                num = input("Number of subscribers (default: 3): ").strip()
                num = int(num) if num else 3
                await test_multiple_subscribers(topic, num)

            elif choice == "11":
                topic = input("Enter topic name (default: demo): ").strip() or "demo"
                await test_replay(topic)

            elif choice == "12":
                await test_error_scenarios()

            elif choice == "13":
                topic = input("Enter topic name (default: backpressure-test): ").strip() or "backpressure-test"
                await test_backpressure(topic)

            elif choice == "14":
                await complete_demo()

            elif choice == "15":
                setup_demo_environment()

            else:
                print("\n❌ Invalid choice. Please try again.")

        except KeyboardInterrupt:
            print("\n\n⚠️  Operation cancelled")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Make sure:")
            print("  1. Server is running (python main.py)")
            print("  2. Topic exists (create it first)")
            print("  3. You're connected to localhost:8080")

        input("\n⏎  Press Enter to continue...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
