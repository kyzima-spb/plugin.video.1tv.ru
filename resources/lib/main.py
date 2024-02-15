from codequick import Route, Resolver, Listitem, run
import urlquick

from .parsers import (
    EpisodeCollection,
    parse_shows,
    parse_show_menu,
)


@Route.register
def root(plugin):
    """Отображает алфавитный указатель."""
    for label, links in parse_shows('/shows?all'):
        yield Listitem.from_dict(tv_show_list, label=label, params={
            'links': links,
        })


@Route.register
def tv_show_list(plugin, links):
    """Отображает список шоу под выбранной буквой."""
    for url, label in links:
        yield Listitem.from_dict(episodes_menu, label=label, params={
            'url': url,
        })


@Route.register
def episodes_menu(plugin, url):
    """Отображает пункты меню для выбранного шоу."""
    for url, label in parse_show_menu(url):
        yield Listitem.from_dict(episodes_list, label=label, params={
            'url': url,
        })


@Route.register
def episodes_list(plugin, url):
    """Отображает список эпизодов выбранного шоу."""
    episodes = EpisodeCollection.parse(url)

    for item_data in episodes:
        yield Listitem.from_dict(play_video, **item_data)

    # Extract the next page url if one exists.
    next_url = episodes.next_url
    if next_url is not None:
        yield Listitem.next_page(url=next_url)


@Resolver.register
def play_video(plugin, url):
    """Воспроизводит видео файл."""
    video_url = plugin.extract_source(url)

    resp = urlquick.get(url)
    label = resp.parse('title').text

    return Listitem.from_dict(
        video_url,
        label,
        properties={
            'inputstream': 'inputstream.adaptive',
            'inputstream.adaptive.manifest_type': 'hls',
        },
    )
