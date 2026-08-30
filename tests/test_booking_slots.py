from pond.booking_slots import logical_slot, slot_group, slot_identity


def test_pond_schedule_aliases_share_logical_slot_ids() -> None:
	assert slot_identity("Men's", "15:45-16:45") == "P4"
	assert slot_identity("Mixed", "15:40-16:40") == "P4"
	assert slot_identity("Ladies", "17:00-18:00") == "P5"
	assert slot_identity("Men's", "16:50-17:50") == "P5"
	assert slot_identity("Mixed", "18:15-19:15") == "P6"
	assert slot_identity("Men's", "18:00-19:00") == "P6"


def test_venue_distinguishes_pond_and_lido_slots() -> None:
	assert slot_group("Lido") == "lido"
	assert slot_group("Men's") == "pond"
	assert slot_identity("Lido", "18:00-20:00") == "L3"
	assert logical_slot("Lido", "18:00-19:00") is None


def test_unmatched_slot_gets_visible_fallback_identity() -> None:
	assert slot_identity("Mixed", "16:05-17:05") == "unmatched:pond:16:05-17:05"