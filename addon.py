from codequick import Route, Resolver, Listitem, utils, run
from codequick.utils import urljoin_partial
import urlquick


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


def parse_shows():
    url = url_constructor('/shows?all')
    resp = urlquick.get(url)

    root_elem = resp.parse('section', attrs={
        'class': 'archive',
    })

    for elem in root_elem.iterfind(".//div[@class='card']"):
        letter = elem.find("div[@class='letter']").text.strip().upper()
        links = [(a.get('href'), a.text.strip()) for a in elem.findall('a')]
        yield letter, links


@Route.register
def root(plugin):
    for label, links in parse_shows():
        item = Listitem()
        item.label = label
        item.set_callback(tv_show_list, links=links)
        yield item


@Route.register
def tv_show_list(plugin, links):
    for url, label in links:
        item = Listitem()
        item.label = label
        item.set_callback(episodes_menu, url=url)
        yield item


@Route.register
def episodes_menu(plugin, url):
    resp = urlquick.get(url_constructor(url))
    menu_elem = resp.parse('div', attrs={'class': 'menu'})

    for elem in menu_elem.iterfind('ul/li/a'):
        url = elem.get('href')
        label = elem.find('span').text.strip()

        item = Listitem()
        item.label = label
        item.set_callback(episodes_list, url=url)
        yield item


@Route.register
def episodes_list(plugin, url):
    resp = urlquick.get(url_constructor(url))
    root_elem = resp.parse(attrs={'data-type': 'content_modal'})

    for elem in root_elem.iterfind('.//a[@data-role="content_modal"]'):
        item = Listitem()

        item.label = find_text(
            elem, './/h3', './/div[@class="title"]'
        )
        item.info['plot'] = find_text(
            elem, './/div[@class="itv-index-card__text"]', './/div[@class="lead"]'
        )
        item.info['duration'] = find_text(elem, './/div[@class="length"]')

        cover = elem.find('.//img').attrib
        cover_url = cover.get('src' if 'src' in cover else 'data-src')
        item.art['thumb'] = url_constructor(cover_url)

        item.set_callback(play_video, url=elem.get('href'))

        yield item


@Resolver.register
def play_video(plugin, url):
    url = url_constructor(url)
    return plugin.extract_source(url)


if __name__ == '__main__':
    run()
