"""
Xity Sleep Bible — Theme Rotation Configuration

8-theme cycle keyed by ISO week number.
Each theme maps to a background video filename in assets/backgrounds/.
Themes auto-rotate week-by-week via modulo arithmetic.
"""

THEMES = [
    {
        "name": "Forest",
        "description": (
            "A dense, ancient forest at night. Rain drips from leaves. "
            "Owls call softly in the distance. The air smells of pine and cold earth."
        ),
        "bg_video": "forest_loop.mp4",
        "sensory_anchors": [
            "pine resin", "cold moss", "dripping rain", "rustling canopy", "distant creek"
        ],
    },
    {
        "name": "Ocean",
        "description": (
            "A quiet shoreline under a crescent moon. Gentle waves break and retreat. "
            "Salt air. The horizon glows faintly with phosphorescence."
        ),
        "bg_video": "ocean_loop.mp4",
        "sensory_anchors": [
            "salt air", "wet sand", "rhythmic tides", "bioluminescent foam", "far horizon"
        ],
    },
    {
        "name": "Mountain Cabin",
        "description": (
            "A warm log cabin high in snow-covered mountains. "
            "A fire burns low in the hearth. Frost forms on the single window."
        ),
        "bg_video": "cabin_loop.mp4",
        "sensory_anchors": [
            "cedar smoke", "wool blanket", "crackling embers", "frost on glass", "burnt pine"
        ],
    },
    {
        "name": "Night Sky",
        "description": (
            "Open countryside, zero light pollution. The Milky Way stretches overhead. "
            "Absolute silence at altitude. The earth cooling slowly beneath you."
        ),
        "bg_video": "night_sky_loop.mp4",
        "sensory_anchors": [
            "cool grass", "vast starfield", "cold dew", "infinite depth", "stone beneath"
        ],
    },
    {
        "name": "Rain on Glass",
        "description": (
            "Inside a warm apartment. Heavy rain slides down the window. "
            "City lights blur into soft watercolor streaks behind the glass."
        ),
        "bg_video": "rain_glass_loop.mp4",
        "sensory_anchors": [
            "warm tea", "lamplight", "rain percussion", "fogged glass", "soft cushions"
        ],
    },
    {
        "name": "Desert Silence",
        "description": (
            "A vast high desert at 3 AM. No wind. Stars fixed and immovable. "
            "The rock still radiating the day's heat while the air above turns cold."
        ),
        "bg_video": "desert_loop.mp4",
        "sensory_anchors": [
            "warm sandstone", "cold night air", "absolute stillness", "mineral dust", "deep shadow"
        ],
    },
    {
        "name": "Ancient Library",
        "description": (
            "A candlelit room behind tall oak shelves, ten thousand books. "
            "A sleeping cat on the reading chair. The ticking of an unseen clock."
        ),
        "bg_video": "library_loop.mp4",
        "sensory_anchors": [
            "aged paper", "beeswax", "leather spines", "slow clock", "hearth warmth"
        ],
    },
    {
        "name": "Candlelit Room",
        "description": (
            "A single room. One candle. Soft amber shadows on bare walls. "
            "Everything slowing. Only your breath and the faint sound of settling."
        ),
        "bg_video": "candle_loop.mp4",
        "sensory_anchors": [
            "melting wax", "amber light", "linen weight", "fading scent", "absolute stillness"
        ],
    },
]


def get_theme_for_week(iso_week: int) -> dict:
    """
    Return the theme dict for a given ISO week number.

    Purpose:
        Auto-rotate through 8 themes using modulo arithmetic so no two consecutive
        uploads share a theme. Deterministic — same week always returns same theme.

    Args:
        iso_week (int): ISO calendar week number (1–53).

    Returns:
        dict: Theme dict with keys: name, description, bg_video, sensory_anchors.

    Error conditions:
        None — pure function, no external dependencies.
    """
    return THEMES[(iso_week - 1) % len(THEMES)]
