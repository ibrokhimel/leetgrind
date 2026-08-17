from dataclasses import dataclass


@dataclass(frozen=True)
class Problem:
    id: int
    slug: str
    title: str
    difficulty: str
    tags: tuple[str, ...]
    is_paid_only: bool
    stub: str | None
    content_html: str | None

    @property
    def folder_name(self) -> str:
        return f"{self.id:04d}-{self.slug}"
