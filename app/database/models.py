from typing import List, Optional
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.sql import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class Trader(Base):
    """Model representing a trader/user in the system."""
    __tablename__ = "traders"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    address: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    last_tracked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships
    state_history: Mapped[List["UserStateHistory"]] = relationship(
        "UserStateHistory",
        back_populates="trader",
        cascade="all, delete-orphan"
    )
    trade_events: Mapped[List["TradeEvent"]] = relationship(
        "TradeEvent",
        back_populates="trader",
        cascade="all, delete-orphan"
    )
    leaderboard_metric: Mapped[Optional["LeaderboardMetric"]] = relationship(
        "LeaderboardMetric",
        back_populates="trader",
        uselist=False,
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Trader(id={self.id}, address={self.address}, active={self.is_active})>"


class UserStateHistory(Base):
    """Model for storing historical user state snapshots from Hyperliquid API."""
    __tablename__ = "user_state_history"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    trader_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("traders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    state_data: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Raw JSON response from Hyperliquid userState endpoint"
    )
    
    # Relationship
    trader: Mapped["Trader"] = relationship("Trader", back_populates="state_history")
    
    def __repr__(self) -> str:
        return f"<UserStateHistory(id={self.id}, trader_id={self.trader_id}, timestamp={self.timestamp})>"


class TradeEvent(Base):
    """Model for tracking trading events and position changes."""
    __tablename__ = "trade_events"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    trader_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("traders.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    event_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        comment="Event type: OPEN_POSITION, CLOSE_POSITION, MODIFY_POSITION, etc."
    )
    details: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        comment="Event details like coin, size, entry_price, side, etc."
    )
    
    # Relationship
    trader: Mapped["Trader"] = relationship("Trader", back_populates="trade_events")
    
    def __repr__(self) -> str:
        return f"<TradeEvent(id={self.id}, trader_id={self.trader_id}, type={self.event_type})>"


class LeaderboardMetric(Base):
    """Model for storing calculated leaderboard metrics for each trader."""
    __tablename__ = "leaderboard_metrics"
    
    trader_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("traders.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    account_age_days: Mapped[int] = mapped_column(Integer, nullable=False)
    total_volume_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    win_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Win rate as decimal (0.55 = 55%)"
    )
    avg_risk_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_profit_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_loss_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    
    # Relationship
    trader: Mapped["Trader"] = relationship("Trader", back_populates="leaderboard_metric")
    
    def __repr__(self) -> str:
        return f"<LeaderboardMetric(trader_id={self.trader_id}, win_rate={self.win_rate:.2%})>"
