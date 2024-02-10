from functools import partial
import html
import re
from urllib.parse import urljoin

import htmlement
import urlquick

try:
    from codequick.utils import strip_tags, urljoin_partial
except ImportError:
    def urljoin_partial(base_url):
        return partial(urljoin, base_url)


BASE_URL = 'https://www.1tv.ru'
url_constructor = urljoin_partial(BASE_URL)


def find_first(elem, *xpath):
    for i in xpath:
        found = elem.find(i)
        if found is not None:
            return found
    return None


def find_text(elem, *xpath):
    found = find_first(elem, *xpath)
    return ''.join(found.itertext()) if found is not None else ''


def parse_shows(url: str):
    resp = urlquick.get(url_constructor(url))

    root_elem = resp.parse('section', attrs={
        'class': 'archive',
    })

    for elem in root_elem.iterfind(".//div[@class='card']"):
        letter = elem.find("div[@class='letter']").text.strip().upper()
        links = [(a.get('href'), a.text.strip()) for a in elem.iterfind('a')]
        yield letter, links


def parse_show_menu(url):
    resp = urlquick.get(url_constructor(url))
    menu_elem = resp.parse('div', attrs={'class': 'menu'})

    for elem in menu_elem.iterfind('ul/li/a'):
        yield elem.get('href'), elem.find('span').text.strip()


class EpisodeCollection:
    def __init__(self, root_elem, next_url=None):
        self._root_elem = root_elem
        self._next_url = next_url

    def __iter__(self):
        for elem in self._root_elem.iterfind('.//a[@data-role="content_modal"]'):
            cover = elem.find('.//img').attrib
            cover_url = cover.get('src' if 'src' in cover else 'data-src')
            yield {
                'label': find_text(
                    elem,
                    './/h3',
                    './/div[@class="title"]',
                ),
                'info': {
                    'plot': find_text(
                        elem,
                        './/div[@class="itv-index-card__text"]',
                        './/div[@class="lead"]',
                    ),
                    'duration': find_text(elem, './/div[@class="length"]')
                },
                'art': {
                    'thumb': url_constructor(cover_url),
                },
                'params': {
                    'url': url_constructor(elem.get('href')),
                },
            }

    @property
    def next_url(self):
        if self._next_url is not None:
            if self.parse(self._next_url) is not None:
                return self._next_url
        return None

    @classmethod
    def from_html(cls, root_elem):
        next_url = None

        next_elem = root_elem.find('.//*[.="Показать еще"]')
        if next_elem is not None:
            next_url = next_elem.get('data-url')

        return cls(root_elem=root_elem, next_url=next_url)

    @classmethod
    def from_javascript(cls, code: str):
        def find_root_element():
            pattern = r"collection_items\s*=\s*.*'<(.+)>'"
            match = re.search(pattern, code)
            return None if not match else htmlement.fromstring(
                match.group(1).replace('\\', '')
            )

        def find_next_url():
            pattern = r'''('|")data-url\1,\s*('|")(.+?)\2'''
            match = re.search(pattern, code)
            if match is not None:
                return html.unescape(match.group(3))
            return None

        root_elem = find_root_element()

        if root_elem is None:
            return None
        
        return cls(root_elem=root_elem, next_url=find_next_url())

    @classmethod
    def parse(cls, url: str):
        resp = urlquick.get(url_constructor(url))
        content_type = resp.headers.get('content-type')

        if content_type.startswith('text/javascript'):
            return cls.from_javascript(resp.text)
        else:
            return cls.from_html(resp.parse())


if __name__ == '__main__':
    import time

    episodes = EpisodeCollection.parse('https://www.1tv.ru/shows/kto-hochet-stat-millionerom/vypuski')
    # episodes = EpisodeCollection.parse('https://www.1tv.ru/shows/chto-gde-kogda/vypuski')
    # episodes = EpisodeCollection.parse('https://www.1tv.ru/shows/byt-ryadom/vypuski')
    # episodes = EpisodeCollection.parse('https://www.1tv.ru/shows/davay-pozhenimsya/vypuski-i-luchshie-momenty')

    while episodes.next_url is not None:
        print(episodes.next_url)
        episodes = EpisodeCollection.parse(episodes.next_url)
        time.sleep(1)
