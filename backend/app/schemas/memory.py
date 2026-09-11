from typing import Optional

from pydantic import BaseModel


class MemorySearchResult(BaseModel):
    id: str
    source_type: str
    content_item_id: Optional[str] = None
    text: str
