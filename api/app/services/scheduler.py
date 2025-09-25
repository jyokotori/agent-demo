"""Mock scheduling service used by the reservation agent."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
import logging
from threading import Lock
from typing import Optional
import uuid


class ReservationStatus(str, Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class ReservationRecord:
    reservation_id: str
    session_id: str
    resource_id: str
    start_time: datetime
    end_time: datetime
    status: ReservationStatus

    def as_dict(self) -> dict[str, str]:
        return {
            "reservation_id": self.reservation_id,
            "resource_id": self.resource_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "status": self.status.value,
        }


class MockScheduler:
    """A lightweight, in-memory mock to emulate device scheduling."""

    def __init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self._lock = Lock()
        self._reservations: dict[str, ReservationRecord] = {}
        self._busy_slots: set[datetime] = set()

    @staticmethod
    def _normalize_start(start_time: datetime) -> datetime:
        aware = start_time.astimezone(UTC)
        return aware.replace(minute=0, second=0, microsecond=0)

    def _is_slot_available(self, start_time: datetime) -> bool:
        slot = self._normalize_start(start_time)
        return slot not in self._busy_slots

    def _generate_slot(self, start_time: datetime) -> tuple[datetime, datetime]:
        slot_start = self._normalize_start(start_time)
        return slot_start, slot_start + timedelta(hours=1)

    def _find_reservation_by_slot(self, slot_start: datetime) -> Optional[ReservationRecord]:
        for record in self._reservations.values():
            if record.start_time == slot_start and record.status == ReservationStatus.CONFIRMED:
                return record
        return None

    def check_availability(self, *, start_time: datetime) -> dict[str, object]:
        """Return device availability without changing scheduler state."""

        slot_start, slot_end = self._generate_slot(start_time)
        with self._lock:
            if not self._is_slot_available(slot_start):
                existing = self._find_reservation_by_slot(slot_start)
                self._logger.debug(
                    "slot unavailable",
                    extra={
                        "event": "availability",
                        "available": False,
                        "slot_start": slot_start.isoformat(),
                    },
                )
                return {
                    "intent": "availability",
                    "action_required": False,
                    "available": False,
                    "reason": "Requested timeslot is already reserved.",
                    "reservation": existing.as_dict() if existing else None,
                }

            self._logger.debug(
                "slot available",
                extra={
                    "event": "availability",
                    "available": True,
                    "slot_start": slot_start.isoformat(),
                },
            )
            return {
                "intent": "availability",
                "action_required": False,
                "available": True,
                "proposal": {
                    "resource_id": "device-001",
                    "start_time": slot_start.isoformat(),
                    "end_time": slot_end.isoformat(),
                },
            }

    def book_reservation(self, *, session_id: str, start_time: datetime) -> dict[str, object]:
        """Attempt to book a slot. Returns reservation details or failure reason."""

        with self._lock:
            slot_start, slot_end = self._generate_slot(start_time)

            existing = self._find_reservation_by_slot(slot_start)
            if existing:
                if existing.session_id == session_id:
                    self._logger.debug(
                        "reservation already exists",
                        extra={
                            "event": "booking",
                            "success": True,
                            "reservation_id": existing.reservation_id,
                            "session_id": session_id,
                        },
                    )
                    return {
                        "intent": "booking_result",
                        "action_required": False,
                        "action": "confirm",
                        "success": True,
                        "reservation": existing.as_dict(),
                        "note": "Reservation already confirmed for this session.",
                    }
                self._logger.debug(
                    "booking failed: slot busy",
                    extra={
                        "event": "booking",
                        "success": False,
                        "slot_start": slot_start.isoformat(),
                        "session_id": session_id,
                    },
                )
                return {
                    "intent": "booking_result",
                    "action_required": False,
                    "action": "confirm",
                    "success": False,
                    "reason": "Requested timeslot is already reserved.",
                }

            reservation_id = uuid.uuid4().hex
            record = ReservationRecord(
                reservation_id=reservation_id,
                session_id=session_id,
                resource_id="device-001",
                start_time=slot_start,
                end_time=slot_end,
                status=ReservationStatus.CONFIRMED,
            )

            self._reservations[reservation_id] = record
            self._busy_slots.add(slot_start)
            self._logger.debug(
                "reservation confirmed",
                extra={
                    "event": "booking",
                    "success": True,
                    "reservation_id": reservation_id,
                    "session_id": session_id,
                },
            )

            return {
                "intent": "booking_result",
                "action_required": False,
                "action": "confirm",
                "success": True,
                "reservation": record.as_dict(),
            }

    def cancel_reservation(self, *, reservation_id: str, session_id: str) -> dict[str, object]:
        with self._lock:
            record = self._reservations.get(reservation_id)
            if not record or record.session_id != session_id:
                self._logger.debug(
                    "cancel failed: not found",
                    extra={
                        "event": "booking",
                        "action": "cancel",
                        "success": False,
                        "reservation_id": reservation_id,
                        "session_id": session_id,
                    },
                )
                return {
                    "intent": "booking_result",
                    "action": "cancel",
                    "action_required": False,
                    "success": False,
                    "reason": "Reservation not found for session.",
                }

            if record.status == ReservationStatus.CANCELLED:
                return {
                    "intent": "booking_result",
                    "action": "cancel",
                    "action_required": False,
                    "success": False,
                    "reason": "Reservation already cancelled.",
                    "reservation": record.as_dict(),
                }

            if record.status != ReservationStatus.CONFIRMED:
                return {
                    "intent": "booking_result",
                    "action": "cancel",
                    "action_required": False,
                    "success": False,
                    "reason": f"Reservation already {record.status.value}.",
                    "reservation": record.as_dict(),
                }

            self._busy_slots.discard(record.start_time)
            record.status = ReservationStatus.CANCELLED
            self._logger.debug(
                "reservation cancelled",
                extra={
                    "event": "booking",
                    "action": "cancel",
                    "success": True,
                    "reservation_id": reservation_id,
                    "session_id": session_id,
                },
            )
            return {
                "intent": "booking_result",
                "action": "cancel",
                "action_required": False,
                "success": True,
                "reservation": record.as_dict(),
            }


scheduler_service = MockScheduler()
