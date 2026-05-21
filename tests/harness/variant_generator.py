from __future__ import annotations

import random
import re
import unicodedata
from typing import List


class VariantGenerator:
    def __init__(self, seed: int):
        self.seed = seed
        self._rng = random.Random(seed)

    def _drop_accents(self, text: str) -> str:
        n = unicodedata.normalize("NFD", text)
        return "".join(ch for ch in n if unicodedata.category(ch) != "Mn")

    def _typo_swap(self, text: str) -> str:
        if len(text) < 5:
            return text
        idx = self._rng.randint(1, len(text) - 2)
        chars = list(text)
        chars[idx - 1], chars[idx] = chars[idx], chars[idx - 1]
        return "".join(chars)

    def _partial(self, text: str) -> str:
        parts = text.split()
        if len(parts) <= 2:
            return text
        keep = self._rng.randint(2, min(4, len(parts)))
        return " ".join(parts[:keep])

    def _natural_prefix(self, text: str) -> str:
        templates = [
            "hola, {t}",
            "quiero {t}",
            "me pasas {t}",
            "búscame {t}",
        ]
        tpl = self._rng.choice(templates)
        return tpl.format(t=text)

    def generate(self, text: str, max_variants: int = 5) -> List[str]:
        base = text.strip()
        variants = [
            base,
            base.lower(),
            self._drop_accents(base),
            self._typo_swap(base),
            self._partial(base),
            self._natural_prefix(base),
            re.sub(r"\s+", " ", base).strip(),
        ]

        out: List[str] = []
        for v in variants:
            vv = v.strip()
            if vv and vv not in out:
                out.append(vv)
            if len(out) >= max_variants:
                break
        return out

