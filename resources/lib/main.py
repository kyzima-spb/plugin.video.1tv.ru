import json
import typing as t

from kodi_useful import (
    router,
    Addon,
    Directory,
)
from kodi_useful.enums import Content, Scope
import xbmcgui
import xbmcplugin

from .parsers import (
    get_episodes,
    get_shows,
    get_show_albums,
    get_video,
)


addon = Addon(
    # locale_map_file='resources/language/locale_map.json',
)


def main():
    addon.dispatch()


@router.route(is_root=True)
@Directory(
    ltitle='Алфавитный указатель',
    content=Content.ALBUMS,
    cache_to_disk=False,
)
def index(addon: Addon):
    """Отображает алфавитный указатель."""
    for label, links in get_shows():
        url = addon.url_for(list_tv_shows, links=json.dumps(links))
        item = xbmcgui.ListItem(label)
        yield url, item, True


@router.route
@Directory(
    # ltitle='albums',
    content=Content.ALBUMS,
    cache_to_disk=False,
)
def list_tv_shows(
    addon: Addon,
    links: t.Annotated[str, Scope.QUERY],
):
    """Отображает список шоу под выбранной буквой."""
    for url, label in json.loads(links):
        url = addon.url_for(episodes_menu, url=url)
        yield url, xbmcgui.ListItem(label), True


@router.route
@Directory(
    # ltitle='albums',
    content=Content.ALBUMS,
    cache_to_disk=False,
)
def episodes_menu(
    addon: Addon,
    url: t.Annotated[str, Scope.QUERY],
):
    """Отображает пункты меню для выбранного шоу."""
    for page_url, label in get_show_albums(url):
        url = addon.url_for(list_episodes, page_url=page_url)
        item = xbmcgui.ListItem(label)
        yield url, item, True


@router.route
@Directory(
    # ltitle='albums',
    content=Content.VIDEOS,
    cache_to_disk=False,
)
def list_episodes(
    addon: Addon,
    page_url: t.Annotated[str, Scope.QUERY],
):
    """Отображает список эпизодов выбранного шоу."""
    episodes, next_page_url = get_episodes(page_url)

    for show in episodes:
        url = addon.url_for(play_video, video_id=show.id)
        item = xbmcgui.ListItem(show.title)
        item.setProperty('IsPlayable', 'true')
        item.setInfo('video', {
            'plot': show.description,
            'duration': show.duration,
            # 'genre': video['platform'],
        })
        item.setArt({
            'thumb': show.cover,
            # 'icon': video['photo_320'],
        })
        yield url, item, False

    if next_page_url is not None:
        next_url = addon.url_for(list_episodes, page_url=next_page_url)
        next_item = xbmcgui.ListItem('Следующая страница')
        yield next_url, next_item, True


@router.route
def play_video(video_id: t.Annotated[str, Scope.QUERY]):
    """Воспроизводит видео файл."""
    video = get_video(video_id)

    item = xbmcgui.ListItem(video.title, offscreen=True)
    item.setPath(video.play_url)

    # if 'dash' in video['best_fmt']:
    #     item.setProperty('inputstream', 'inputstream.adaptive')
    #     item.setProperty('inputstream.adaptive.manifest_type', 'mpd')
    # elif 'hls' in video['best_fmt']:
    #     item.setProperty('inputstream', 'inputstream.adaptive')
    #     item.setProperty('inputstream.adaptive.manifest_type', 'hls')

    item.setProperty('inputstream', 'inputstream.adaptive')
    item.setProperty('inputstream.adaptive.manifest_type', 'hls')

    xbmcplugin.setResolvedUrl(addon.handle, True, item)
