from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_value(v: Any) -> Any:
    if v is None:
        return None
    if not isinstance(v, str):
        return v
    s = v.strip().replace("\ufeff", "")
    return s if s != "" else None


def _detect_encoding(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            raw.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "latin-1"


def _detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        return dialect.delimiter
    except Exception:
        return ";" if ";" in sample else ","


def _row_is_noise(row: Dict[str, Any]) -> bool:
    vals = [(v or "") for v in row.values()]
    if not any(vals):
        return True

    upper_vals = {str(v).strip().upper() for v in vals if v}
    embedded_markers = {"PKEY", "LINEA", "FECHA", "OPERARIO", "TEXTO"}
    if len(upper_vals.intersection(embedded_markers)) >= 3:
        return True
    return False


@dataclass
class LoadedDataset:
    name: str
    path: str
    sha256: str
    loaded_at_utc: str
    delimiter_detected: str
    encoding_detected: str
    row_count_loaded: int
    rows: List[Dict[str, Any]]

    def snapshot(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.name,
            "path": self.path,
            "sha256": self.sha256,
            "row_count_loaded": self.row_count_loaded,
            "loaded_at_utc": self.loaded_at_utc,
            "delimiter_detected": self.delimiter_detected,
            "encoding_detected": self.encoding_detected,
        }


def load_csv_dataset(name: str, path: str) -> LoadedDataset:
    fp = Path(path)
    raw = fp.read_bytes()
    sha256 = hashlib.sha256(raw).hexdigest()
    encoding = _detect_encoding(raw)
    text = raw.decode(encoding, errors="replace")
    delimiter = _detect_delimiter(text[:4000])

    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    rows: List[Dict[str, Any]] = []
    for rr in reader:
        cleaned = {str(k).strip(): _clean_value(v) for k, v in rr.items()}
        if _row_is_noise(cleaned):
            continue
        rows.append(cleaned)

    return LoadedDataset(
        name=name,
        path=str(fp),
        sha256=sha256,
        loaded_at_utc=_now_utc(),
        delimiter_detected=delimiter,
        encoding_detected=encoding,
        row_count_loaded=len(rows),
        rows=rows,
    )


def load_demo_datasets(name_to_path: Dict[str, str]) -> Tuple[Dict[str, LoadedDataset], List[Dict[str, Any]]]:
    loaded: Dict[str, LoadedDataset] = {}
    snapshots: List[Dict[str, Any]] = []
    for name, path in name_to_path.items():
        ds = load_csv_dataset(name, path)
        loaded[name] = ds
        snapshots.append(ds.snapshot())
    return loaded, snapshots

