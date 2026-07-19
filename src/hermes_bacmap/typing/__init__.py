"""Serotyping: V. parahaemolyticus (O/K), Shigella, E. coli O:H."""

from .ecoh_serotyper import SerotypeResult as EcoHSerotypeResult
from .ecoh_serotyper import serotype as ecoh_serotype
from .shigella_serotyper import ShigellaSerotypeResult
from .shigella_serotyper import serotype as shigella_serotype
from .vpa_serotyper import SerotypeResult as VpaSerotypeResult
from .vpa_serotyper import VpaSerotyper

__all__ = [
    "EcoHSerotypeResult",
    "ShigellaSerotypeResult",
    "VpaSerotypeResult",
    "VpaSerotyper",
    "ecoh_serotype",
    "shigella_serotype",
]
