from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LogicalSlot:
	id: str
	group: str
	times: tuple[str, ...]


LOGICAL_SLOTS = (
	LogicalSlot("P1", "pond", ("12:00-13:00",)),
	LogicalSlot("P2", "pond", ("13:15-14:15",)),
	LogicalSlot("P3", "pond", ("14:30-15:30",)),
	LogicalSlot("P4", "pond", ("15:45-16:45", "15:40-16:40")),
	LogicalSlot("P5", "pond", ("17:00-18:00", "16:50-17:50")),
	LogicalSlot("P6", "pond", ("18:15-19:15", "18:00-19:00")),
	LogicalSlot("P7", "pond", ("19:30-20:30",)),
	LogicalSlot("L1", "lido", ("10:30-13:30",)),
	LogicalSlot("L2", "lido", ("14:30-17:30",)),
	LogicalSlot("L3", "lido", ("18:00-20:00",)),
)


def slot_group(location: str) -> str:
	return "lido" if location == "Lido" else "pond"


def logical_slot(location: str, slot_time: str) -> LogicalSlot | None:
	group = slot_group(location)
	return next(
		(slot for slot in LOGICAL_SLOTS if slot.group == group and slot_time in slot.times),
		None,
	)


def slot_identity(location: str, slot_time: str) -> str:
	mapped = logical_slot(location, slot_time)
	if mapped is not None:
		return mapped.id
	return f"unmatched:{slot_group(location)}:{slot_time}"