"""
Data models for the Pub/Sub system.
Defines all message structures used in WebSocket communication and REST APIs.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, Literal
from datetime import datetime
from enum import Enum


class ErrorCode(str, Enum):
    """Error codes for various failure scenarios"""
    BAD_REQUEST = "BAD_REQUEST"
    TOPIC_NOT_FOUND = "TOPIC_NOT_FOUND"
    SLOW_CONSUMER = "SLOW_CONSUMER"
    UNAUTHORIZED = "UNAUTHORIZED"
    INTERNAL = "INTERNAL"


# ============================================================================
# Client → Server Message Models
# ============================================================================

class Message(BaseModel):
    """Represents a message payload with ID and content"""
    id: str = Field(..., description="Unique message identifier (UUID)")
    payload: Any = Field(..., description="Message content (arbitrary JSON)")


class ClientMessage(BaseModel):
    """Base model for client-to-server WebSocket messages"""
    type: Literal["subscribe", "unsubscribe", "publish", "ping"]
    topic: Optional[str] = None
    message: Optional[Message] = None
    client_id: Optional[str] = None
    last_n: Optional[int] = Field(default=0, description="Number of historical messages to replay")
    request_id: Optional[str] = Field(default=None, description="Correlation ID for request/response")


# ============================================================================
# Server → Client Message Models
# ============================================================================

class ErrorDetail(BaseModel):
    """Error information structure"""
    code: ErrorCode
    message: str


class ServerMessage(BaseModel):
    """Base model for server-to-client WebSocket messages"""
    type: Literal["ack", "event", "error", "pong", "info"]
    request_id: Optional[str] = None
    topic: Optional[str] = None
    message: Optional[Message] = None
    error: Optional[ErrorDetail] = None
    status: Optional[str] = None
    msg: Optional[str] = None
    ts: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# ============================================================================
# REST API Models
# ============================================================================

class CreateTopicRequest(BaseModel):
    """Request body for creating a new topic"""
    name: str = Field(..., description="Topic name")


class CreateTopicResponse(BaseModel):
    """Response for successful topic creation"""
    status: str = "created"
    topic: str


class DeleteTopicResponse(BaseModel):
    """Response for successful topic deletion"""
    status: str = "deleted"
    topic: str


class TopicInfo(BaseModel):
    """Information about a single topic"""
    name: str
    subscribers: int


class ListTopicsResponse(BaseModel):
    """Response containing list of all topics"""
    topics: list[TopicInfo]


class HealthResponse(BaseModel):
    """System health information"""
    uptime_sec: int
    topics: int
    subscribers: int


class TopicStats(BaseModel):
    """Statistics for a single topic"""
    messages: int
    subscribers: int


class StatsResponse(BaseModel):
    """Response containing per-topic statistics"""
    topics: dict[str, TopicStats]
