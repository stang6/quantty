#core/storage/writers.py
import csv
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict


# -----------------------------------------
# Base Writer (interface)
# -----------------------------------------
class BaseWriter(ABC):
    @abstractmethod
    def write(self, row: Dict):
        """Write a single structured row"""
        pass


# -----------------------------------------
# CSV Writer
# -----------------------------------------
class CSVWriter(BaseWriter):
    def __init__(self, path: str):
        self.path = Path(path)
        self.header_written = False

        # Ensure the parent folder exists
        self.path.parent.mkdir(parents=True, exist_ok=True)

        # Check if header already exists
        if self.path.exists() and self.path.stat().st_size > 0:
            self.header_written = True

    def _write_header(self, fieldnames):
        """Ensure CSV header is written exactly once."""
        with self.path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

    def write(self, row: Dict):
        """Atomic-safe CSV write (via temporary file replace)."""
        fieldnames = list(row.keys())

        # First write header if needed
        if not self.header_written:
            self._write_header(fieldnames)
            self.header_written = True

        # Atomic write: write to .tmp then replace
        tmp_path = self.path.with_suffix(".tmp")

        # Copy existing file to tmp
        if self.path.exists():
            tmp_path.write_bytes(self.path.read_bytes())

        # Append new row to tmp
        with tmp_path.open("a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(row)

        # Replace original file
        os.replace(tmp_path, self.path)

