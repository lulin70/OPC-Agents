"""Shared constants and enum for the skill marketplace modules.

Extracted from ``skill_marketplace`` to break the circular import that would
otherwise arise between the facade (``skill_marketplace``) and the external
marketplace implementation (``skill_marketplace_external``):

* ``DATA_DIR`` is consumed by both ``SkillMarketplace`` (facade) and
  ``ExternalSkillMarketplace`` (external).
* ``TrustLevel`` is consumed by the dataclasses / class that live in
  ``skill_marketplace_external`` (``ExternalSkill``, ``MCPServerInfo``,
  ``ExternalSkillMarketplace``) and is re-exported by the facade for
  backward compatibility.

Both modules import these names from here, so neither has to import from the
other at module load time.
"""

import os
from enum import Enum


DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "marketplace"
)


class TrustLevel(str, Enum):
    OFFICIAL = "official"
    VERIFIED = "verified"
    COMMUNITY = "community"
    UNVERIFIED = "unverified"
