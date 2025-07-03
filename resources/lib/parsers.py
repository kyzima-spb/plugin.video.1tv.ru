from functools import wraps
from datetime import datetime
import xml.etree.ElementTree as et
import re
import typing as t
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode

import htmlement
import requests
from YDWrapper import extract_source

from .models import TVShow, Video


def parse_html(
    html: str,
    tag: str = '',
    attrs: t.Optional[t.Dict[str, str]] = None,
) -> 'ElementProxy':
    parser = htmlement.HTMLement(tag, attrs)
    parser.feed(html)
    return ElementProxy(element=parser.close())


def str_to_seconds(s: str) -> int:
    pairs_count = len(s.split(':'))
    fmt = ':'.join(reversed(('%S', '%M', '%H')[:pairs_count]))
    tm = datetime.strptime(s, fmt)
    return tm.hour * 3600 + tm.minute * 60 + tm.second


class Session(requests.Session):
    def __init__(
        self,
        base_url: str,
        headers=None,
    ):
        super().__init__()

        self._base_url = base_url

        if headers is not None:
            self.headers.update(headers)

    @wraps(requests.Session.request)
    def request(
        self,
        method: t.Union[str, bytes],
        url: t.Union[str, bytes],
        **kwargs: t.Any,
    ) -> requests.Response:
        if self._base_url is not None:
            url = urljoin(self._base_url.rstrip('/'), url.lstrip('/'))
        return super().request(method, url, **kwargs)

    def parse_html(
        self,
        url: t.Union[str, bytes],
        tag: str,
        *,
        attrs: t.Optional[t.Dict[str, str]] = None,
        method: t.Union[str, bytes] = 'get',
        **kwargs: t.Any,
    ) -> 'ElementProxy':
        response = self.request(method, url, **kwargs)
        return parse_html(response.text, tag, attrs)


class ElementProxy:
    # __slots__ = ()

    def __init__(self, element: et.Element) -> None:
        self._element = element

    def __dir__(self):
        return dir(self._element)

    def __getattr__(self, name):
        return getattr(self._element, name)

    def findall(self, xpath: str):
        return list(self.iterfind(xpath))

    def findtext(self, xpath: str, *xpaths: str) -> str:
        found = self.first(xpath, *xpaths)
        return '' if found is None else ''.join(found.itertext())

    def first(self, xpath: str, *xpaths: str) -> t.Optional['ElementProxy']:
        for i in (xpath, *xpaths):
            found = self._element.find(i)
            if found is not None:
                return self.__class__(found)
        return None

    @classmethod
    def fromstring(cls, s: str) -> 'ElementProxy':
        return cls(htmlement.fromstring(s))

    def iterfind(self, xpath: str):
        return (self.__class__(i) for i in self._element.iterfind(xpath))


session = Session(
    base_url='https://www.1tv.ru',
    headers={
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.5993.118 Safari/537.36',
    }
)


def get_shows() -> t.Dict[str, t.Tuple[str, str]]:
    """Возвращает алфавитно-цифровой индекс передач."""
    root_elem = session.parse_html('shows?all', 'section', attrs={
        'class': 'archive',
    })

    for elem in root_elem.iterfind(".//div[@class='card']"):
        letter = elem.findtext("div[@class='letter']").upper()
        links = [(a.get('href'), a.text) for a in elem.iterfind('a')]
        yield letter, links


def get_show_albums(url) -> t.Dict[str, t.Tuple[str, str]]:
    """Возвращает категории для передачи, указанные на сайте."""
    menu_elem = session.parse_html(url, 'div', attrs={'class': 'menu'})

    for elem in menu_elem.iterfind('ul/li/a'):
        yield elem.get('href'), elem.findtext('span')


def get_episodes(url: str) -> t.Tuple[t.Sequence[TVShow], t.Optional[str]]:
    """Возвращает эпизоды передачи."""
    # for elem in self._root_elem.iterfind('.//a[@data-role="content_modal"]'):
    # for elem in self._root_elem.iterfind('.//a[@data-modal-url]'):
    # for elem in self._root_elem.iterfind('.//*[@class="collection_items"]/article'):

    url_pairs = urlparse(url)
    qs = dict(parse_qsl(url_pairs.query))

    limit = int(qs['limit']) if 'limit' in qs else None
    offset = int(qs['offset']) if 'offset' in qs else None

    if limit and offset:
        url = urlunparse(
            url_pairs._replace(query=urlencode({
                'limit': limit + 1,
                'offset': offset,
            }))
        )

    response = session.get(url)
    content_type = response.headers.get('content-type')

    if content_type.startswith('text/javascript'):
        pattern = r"collection_items\s*=\s*.*'<(.+)>'"
        match = re.search(pattern, response.text)

        if not match:
            return (), None

        response_text = match.group(1).replace('\\', '')
    else:
        response_text = response.text

    root_elem = ElementProxy.fromstring(response_text)
    items = root_elem.findall('.//*[@data-id][@data-role="collection_item_card"]')

    if limit is None:
        next_elem = root_elem.find('.//*[.="Показать еще"]')
        next_url = next_elem.get('data-url')
    elif len(items) >= limit:
        next_url = urlunparse(
            url_pairs._replace(query=urlencode({
                'limit': limit,
                'offset': offset + limit,
            }))
        )
    else:
        next_url = None

    return tuple(
        TVShow(
            id=elem.get('data-id'),
            url=elem.find('a').get('href'),
            title=elem.findtext('.//h3', './/div[@class="title"]'),
            description=elem.findtext('.//div[@class="itv-index-card__text"]', './/div[@class="lead"]'),
            duration=(s := elem.findtext('.//div[@class="length"]')) and str_to_seconds(s),
            cover=urljoin(
                session._base_url,
                (attrib := elem.find('.//img').attrib) and (attrib.get('src') or attrib.get('data-src'))
            )
        )
        for elem in items[:limit]
    ), next_url


def get_video(video_id: str) -> Video:
    response = session.get('/playlist?admin=false&single=true&video_id=%s' % video_id)
    response_data = response.json().pop()

    if response_data['material_type'] == 'video_material':
        return Video(title=response_data['title'], play_url=response_data['sources'][0]['src'])

    if response_data['material_type'] == 'external_material':
        info = extract_source(response_data['external_embed_link'])
    else:
        info = extract_source(url)

    return Video(title=info.title, play_url=info.play_url)


if __name__ == '__main__':
    url = '/shows/chto-gde-kogda/vypuski'
    # EpisodeCollection.parse(url)
    # url = '/collections/147/items.js?limit=1&offset=0'
    # url = '/collections/5318/items.js?limit=3&offset=0'
    url = '/collections/147/items.js?limit=12&offset=235&type=rubric&view_type=mosaic'
    # url = '/collections/147/items.js?limit=12&offset=247&type=rubric&view_type=mosaic'
    items, next_url = get_episodes(url)
    print([i.title for i in items], next_url)
