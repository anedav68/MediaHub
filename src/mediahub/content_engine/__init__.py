"""content_engine — MediaHub's single, AI-directed content generation engine.

Every content type produces its draft cards through ``generate_content``: an
AI Director plans the set (platform mix, angle, hook) while avoiding anything
the user has already seen, then the writer turns that plan into platform-ready
caption cards. This is the one engine the four caption stubs and the meet-recap
content tools route through, so there is no separately-coded generator per type.
"""
from .engine import generate_content, generate_caption, load_brand_context
from .director import plan_content_directions

__all__ = [
    "generate_content",
    "generate_caption",
    "load_brand_context",
    "plan_content_directions",
]
