import typing as t


class TVShow(t.NamedTuple):
    id: str
    url: str
    title: str
    description: str
    duration: int
    cover: str


class Video(t.NamedTuple):
    title: str
    play_url: str
