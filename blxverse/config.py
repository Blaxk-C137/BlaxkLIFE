"""Central configuration and balance constants for BLXVERSE.

Everything here is deterministic, server-authoritative, and intentionally
colocated so designers can tune the slice without hunting through modules.
"""

from __future__ import annotations

import os

VERSION = "0.6.0"
SCHEMA_VERSION = 3
SAVE_FORMAT = "blxverse-save"

# ---------------------------------------------------------------------------
# World / simulation
# ---------------------------------------------------------------------------
NPC_COUNT = 72
SPOTLIGHT_COUNT = 18
DAY_START_MINUTE = 7 * 60 + 30          # Monday 07:30 at world creation
TICK_SECONDS = 0.25                      # real seconds between simulation ticks
GAME_MINUTES_PER_TICK = 0.25             # at 1x speed: 1 real second = 1 game minute
MAX_SPEED = 4
ALLOWED_SPEEDS = (0, 1, 2, 4)
WORLD_WIDTH = 1900
WORLD_HEIGHT = 1300
NPC_WALK_SPEED = 55.0                    # world px per game-minute
PLAYER_MAX_SPEED = 230.0                 # real px per second (validated server-side)
PLAYER_RADIUS = 16.0
INTERACT_RADIUS = 115.0                  # in-person interaction range
TALK_RADIUS = 130.0
CALL_MIN_FAMILIARITY = 8.0
INTERACT_PAD = 110.0                     # distance to a venue edge that still counts as "there"
REMOTE_ORDER_FEE = 0.10                  # delivery surcharge for remote shopping
WAGE_BASE = 70                           # shift pay range (before reputation bonus)
WAGE_VARIANCE = 46
DATE_MIN_ROMANCE = 10.0
DATE_MAX_TENSION = 60.0
DATE_LEAD_MINUTES = 120
DATE_DEFAULT_COST = 18
DATE_COSTS = {"restaurant": 42, "cinema": 26, "cafe": 16, "park": 12, "studio": 20, "gallery": 14}

# Tiered intelligence thresholds (design section 4)
FOREGROUND_RADIUS = 260.0
NEARBY_RADIUS = 760.0

# ---------------------------------------------------------------------------
# Economy (fictional, closed-loop BLX; 1 BLX = 1 USD internal reference only)
# ---------------------------------------------------------------------------
STARTING_BALANCE = 320
DAILY_RENT = 32
RENT_HOUR = 9
SHIFT_HOURS = 4
SHIFT_ENERGY_COST = 26
MIN_WAGE = 74
MAX_WAGE = 168
STREET_CART_COST = 250
STREET_CART_DAILY_BASE = 18
MAX_LEDGER_ENTRIES = 400
MAX_WALLET_TXN = 5000
GIFT_SATURATION_CAP = 6                  # repeated identical gifts per week

# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------
REL_MIN = -100.0
REL_MAX = 100.0
FAMILIARITY_MAX = 100.0
TRUST_MAX = 100.0
ROMANCE_MAX = 100.0
TENSION_MAX = 100.0
FLIRT_MIN_FAMILIARITY = 8.0
FLIRT_MIN_TRUST = 12.0
DATE_MIN_FAMILIARITY = 14.0
DATE_MIN_TRUST = 16.0
BREAKUP_TENSION = 74.0
RECONCILE_TENSION = 30.0
RIVAL_TENSION = 62.0

# ---------------------------------------------------------------------------
# Memory / beliefs
# ---------------------------------------------------------------------------
MEMORY_CAP_PER_NPC = 90
MEMORY_RETENTION_DAYS = 45
BELIEF_DECAY_PER_DAY = 0.045
RUMOR_SPREAD_BASE = 0.34
PUBLIC_EVENT_VISIBILITY_RADIUS = 420.0

# ---------------------------------------------------------------------------
# Chaos engine
# ---------------------------------------------------------------------------
CHAOS_TENSION_THRESHOLD = 58.0
CHAOS_COOLDOWN_MINUTES = 480
SECURITY_BAN_HOURS = 6
MAX_BYSTANDERS = 7

# ---------------------------------------------------------------------------
# Feed / messages
# ---------------------------------------------------------------------------
FEED_CAP = 220
FEED_PAGE = 40
THREAD_CAP = 120
MAX_POST_LENGTH = 280
MAX_MESSAGE_LENGTH = 320
MAX_UTTERANCE_LENGTH = 280
MAX_CHAT_LENGTH = MAX_UTTERANCE_LENGTH
MAX_COMMENT_LENGTH = 200
MESSAGE_REPLY_MIN_DELAY = 2.0            # game minutes
MESSAGE_REPLY_MAX_DELAY = 14.0

# ---------------------------------------------------------------------------
# Voice / latency
# ---------------------------------------------------------------------------
VOICE_TARGET_MS = 800
VOICE_METRIC_CAP = 400

# ---------------------------------------------------------------------------
# Optional dialogue LLM (Gemini or an OpenAI-compatible provider key required)
# ---------------------------------------------------------------------------
LLM_MODEL = "gpt-4o-mini"
LLM_BASE_URL = "https://api.openai.com/v1"
LLM_TIMEOUT_SECONDS = 6.0
LLM_MAX_TOKENS = 90
LLM_COST_PER_1K_INPUT = 0.00015
LLM_COST_PER_1K_OUTPUT = 0.0006

# ---------------------------------------------------------------------------
# Safety / server
# ---------------------------------------------------------------------------
MAX_BODY_BYTES = 256 * 1024
ACTION_RATE_LIMIT = 90                   # actions per minute per client
MAX_CHAT_INPUT = 280
RATE_WINDOW_SECONDS = 60
NPC_AGE_RANGE = (22, 68)

# Romance in this slice is adult-only, consent-forward and never identity-gated.
ADULT_AGE_MIN = 22


def data_dir() -> str:
    return os.environ.get("BLXVERSE_DATA_DIR", "data")
