import sys

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, ".")

from community_lenses.ids import fallback_message_id_hash

raw = "<reply1.native@example-list.org>"
print(raw, "->", fallback_message_id_hash(raw))
