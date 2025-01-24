from dataclasses import dataclass
from typing import Optional

@dataclass
class Song:
    """Represents a song with its metadata and state"""
    id: str
    title: str
    duration: int
    thumbnail: str
    webpage_url: str
    is_downloaded: bool = False
    filepath: Optional[str] = None

    @property
    def video_id(self) -> str:
        """Get video ID for tracking"""
        return self.id

    def to_dict(self) -> dict:
        """Convert song to dictionary representation"""
        return {
            'id': self.id,
            'title': self.title,
            'duration': self.duration,
            'thumbnail': self.thumbnail,
            'webpage_url': self.webpage_url,
            'is_downloaded': self.is_downloaded,
            'filepath': self.filepath
        }

    def set_downloaded(self, filepath: str) -> None:
        """Mark song as downloaded and set filepath"""
        self.is_downloaded = True
        self.filepath = filepath

    def get_duration_string(self) -> str:
        """Get formatted duration string"""
        minutes = self.duration // 60
        seconds = self.duration % 60
        return f"{minutes}:{seconds:02d}"