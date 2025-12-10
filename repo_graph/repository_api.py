from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class FileDependencies:
    source_file: Path
    file_dependencies: Optional[List[Path]]
    

@dataclass
class FileUsages:
    source_file: Path
    file_usages: Optional[List[Path]]


class Repository(ABC):

    @abstractmethod
    def find_dependencies(self, file_path: Path) -> FileDependencies:
        """Finds all file dependencies of the specified `file_path` in the repository"""
        pass

    @abstractmethod
    def find_usages(self, file_path: Path) -> FileUsages:
        """Finds all file usages of the specified `file_path` in the repository"""
        pass