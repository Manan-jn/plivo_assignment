"""
Simple example client for the Pub/Sub system.
Demonstrates basic publish and subscribe operations.
"""

import asyncio
import json
import websockets
import uuid


WS_URL = "ws://localhost:8080/ws"


async def simple_subscriber():
    """Simple subscriber example"""
    async with websockets.connect(WS_URL) as websocket:
        # Subscribe to the 'demo' topic
        subscribe_msg = {
            "type": "subscribe",
            "topic": "demo",
            "client_id": "simple-subscriber",
            "last_n": 0  # Don't replay historical messages
        }

        await websocket.send(json.dumps(subscribe_msg))
        print("✓ Subscribed to 'demo' topic")

        # Receive acknowledgment
        ack = await websocket.recv()
        print(f"✓ Server acknowledged: {ack}")

        # Listen for messages
        print("\nListening for messages (press Ctrl+C to stop)...\n")
        try:
            while True:
                message = await websocket.recv()
                data = json.loads(message)

                if data['type'] == 'event':
                    print(f"📩 Received message:")
                    print(f"   Topic: {data['topic']}")
                    print(f"   ID: {data['message']['id']}")
                    print(f"   Payload: {json.dumps(data['message']['payload'], indent=2)}")
                    print(f"   Timestamp: {data['ts']}\n")

        except KeyboardInterrupt:
            print("\nUnsubscribing...")

            # Unsubscribe
            unsubscribe_msg = {
                "type": "unsubscribe",
                "topic": "demo",
                "client_id": "simple-subscriber"
            }
            await websocket.send(json.dumps(unsubscribe_msg))

            # Wait for acknowledgment
            await websocket.recv()
            print("✓ Unsubscribed successfully")


async def simple_publisher():
    """Simple publisher example"""
    async with websockets.connect(WS_URL) as websocket:
        print("✓ Connected to WebSocket")

        # Publish 3 messages
        for i in range(3):
            message_id = str(uuid.uuid4())

            publish_msg = {
                "type": "publish",
                "topic": "demo",
                "message": {
                    "id": message_id,
                    "payload": {
                        "text": f"Hello from simple publisher! Message #{i + 1}",
                        "number": i + 1,
                        "data": {
                            "key1": "value1",
                            "key2": "value2"
                        }
                    }
                }
            }

            await websocket.send(json.dumps(publish_msg))
            print(f"📤 Published message #{i + 1} (ID: {message_id})")

            # Wait for acknowledgment
            ack = await websocket.recv()
            ack_data = json.loads(ack)

            if ack_data['type'] == 'ack':
                print(f"✓ Message #{i + 1} acknowledged by server")
            elif ack_data['type'] == 'error':
                print(f"❌ Error: {ack_data['error']}")

            await asyncio.sleep(1)  # Wait 1 second between messages

        print("\n✓ All messages published successfully")


async def ping_example():
    """Example of ping/pong"""
    async with websockets.connect(WS_URL) as websocket:
        ping_msg = {
            "type": "ping",
            "request_id": "example-ping"
        }

        await websocket.send(json.dumps(ping_msg))
        print("📡 Sent ping")

        response = await websocket.recv()
        data = json.loads(response)

        if data['type'] == 'pong':
            print(f"✓ Received pong (request_id: {data.get('request_id')})")
            print(f"   Server timestamp: {data['ts']}")


def print_menu():
    """Print menu options"""
    print("\n" + "=" * 50)
    print("  Simple Pub/Sub Client")
    print("=" * 50)
    print("\n1. Run as Subscriber (listen for messages)")
    print("2. Run as Publisher (send messages)")
    print("3. Test Ping/Pong")
    print("4. Exit")
    print("\nNote: Make sure to create the 'demo' topic first:")
    print("  curl -X POST http://localhost:8080/topics \\")
    print("       -H 'Content-Type: application/json' \\")
    print("       -d '{\"name\": \"demo\"}'")
    print("=" * 50)


async def main():
    """Main function"""
    while True:
        print_menu()
        choice = input("\nEnter your choice (1-4): ").strip()

        try:
            if choice == "1":
                print("\nStarting subscriber...\n")
                await simple_subscriber()
            elif choice == "2":
                print("\nStarting publisher...\n")
                await simple_publisher()
            elif choice == "3":
                print("\nTesting ping/pong...\n")
                await ping_example()
            elif choice == "4":
                print("\nGoodbye!")
                break
            else:
                print("\n❌ Invalid choice. Please enter 1-4.")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("Make sure the server is running on localhost:8080")

        input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
