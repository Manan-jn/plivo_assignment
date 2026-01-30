"""
Configuration settings for the Pub/Sub system.
All configurable parameters are defined here for easy customization.
"""

import os


class Config:
    """
    Configuration class for the Pub/Sub system.
    Values can be overridden via environment variables.
    """

    # ========================================================================
    # Server Configuration
    # ========================================================================

    # Host address to bind the server to
    HOST = os.getenv("PUBSUB_HOST", "0.0.0.0")

    # Port number for the server
    PORT = int(os.getenv("PUBSUB_PORT", "8080"))

    # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    LOG_LEVEL = os.getenv("PUBSUB_LOG_LEVEL", "INFO")

    # ========================================================================
    # Subscriber Configuration
    # ========================================================================

    # Maximum number of messages in a subscriber's queue before backpressure kicks in
    # When this limit is reached, oldest messages are dropped
    MAX_SUBSCRIBER_QUEUE_SIZE = int(os.getenv("PUBSUB_MAX_QUEUE_SIZE", "100"))

    # ========================================================================
    # Topic Configuration
    # ========================================================================

    # Number of historical messages to retain per topic for replay functionality
    TOPIC_HISTORY_SIZE = int(os.getenv("PUBSUB_HISTORY_SIZE", "100"))

    # ========================================================================
    # WebSocket Configuration
    # ========================================================================

    # WebSocket ping interval (seconds) - server sends ping to clients
    # Set to 0 to disable
    WS_PING_INTERVAL = int(os.getenv("PUBSUB_WS_PING_INTERVAL", "30"))

    # WebSocket ping timeout (seconds) - time to wait for pong response
    WS_PING_TIMEOUT = int(os.getenv("PUBSUB_WS_PING_TIMEOUT", "10"))

    # ========================================================================
    # Performance Configuration
    # ========================================================================

    # Enable/disable detailed performance logging
    ENABLE_PERFORMANCE_LOGGING = os.getenv("PUBSUB_PERF_LOGGING", "false").lower() == "true"

    # ========================================================================
    # Feature Flags
    # ========================================================================

    # Enable message replay functionality (last_n parameter)
    ENABLE_MESSAGE_REPLAY = os.getenv("PUBSUB_ENABLE_REPLAY", "true").lower() == "true"

    # Enable statistics collection
    ENABLE_STATISTICS = os.getenv("PUBSUB_ENABLE_STATS", "true").lower() == "true"


# Create a global config instance
config = Config()


def print_config():
    """Print current configuration (useful for debugging)"""
    print("\n" + "=" * 60)
    print("  Pub/Sub System Configuration")
    print("=" * 60)
    print(f"Host:                        {config.HOST}")
    print(f"Port:                        {config.PORT}")
    print(f"Log Level:                   {config.LOG_LEVEL}")
    print(f"Max Subscriber Queue Size:   {config.MAX_SUBSCRIBER_QUEUE_SIZE}")
    print(f"Topic History Size:          {config.TOPIC_HISTORY_SIZE}")
    print(f"WebSocket Ping Interval:     {config.WS_PING_INTERVAL}s")
    print(f"WebSocket Ping Timeout:      {config.WS_PING_TIMEOUT}s")
    print(f"Message Replay Enabled:      {config.ENABLE_MESSAGE_REPLAY}")
    print(f"Statistics Enabled:          {config.ENABLE_STATISTICS}")
    print(f"Performance Logging:         {config.ENABLE_PERFORMANCE_LOGGING}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Print configuration when run directly
    print_config()
