from __future__ import unicode_literals

import itertools
import json

from .common import InfoExtractor
from ..compat import (
    compat_HTTPError,
    compat_str
)

from ..utils import (
    ExtractorError,
    int_or_none,
    try_get,
    unified_strdate
)

GRAPHQL_ENDPOINT = 'https://murrtube.net/graphql'


class MurrtubeIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?murrtube\.net/videos/.+(?P<id>\b[0-9a-f]{8}\b-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-\b[0-9a-f]{12}\b)'
    _TEST = {
        'url': 'https://murrtube.net/videos/martinibayer-42a6c8f5-cbe9-41f9-8102-c37376e00449',
        'md5': '163bd90c308989cb3b28886c8b16a266',
        'info_dict': {
            'id': '42a6c8f5-cbe9-41f9-8102-c37376e00449',
            'ext': 'mp4',
            'title': 'Bayer x Martini pt.3',
            'description': 'Apparently i got a fox so worked up he managed to third time without as much a pause to catch some breaths! \u003c3\n\nhttps://twitter.com/GayerBayer\nhttps://twitter.com/ADarkMartini',
            'uploader': 'bayer',
            'upload_date': '20181030',
            'published_at': '2018-10-30T19:53:53Z',
            'duration': 126,
            'view_count': int,
            'like_count': int,
            'comment_count': int,
            'tags': list,
            'age_limit': 18
        }
    }

    def _real_extract(self, url):
        video_id = self._match_id(url)
        query = json.dumps({
            "operationName": "Medium",
            "query": """query Medium($id: ID!) {
  medium(id: $id) {
    id
    slug
    title
    description
    key
    duration
    commentsCount
    likesCount
    liked
    viewsCount
    publishedAt
    thumbnailKey
    smallThumbnailKey
    commentsDisabled
    tagList
    visibility
    restriction
    user {
      id
      slug
      name
      avatar
      __typename
    }
    ad {
      title
      description
      url
      avatar
      __typename
    }
    relatedMedia {
      id
      slug
      title
      description
      thumbnailKey
      smallThumbnailKey
      previewKey
      duration
      publishedAt
      restriction
      user {
        id
        slug
        name
        __typename
      }
      __typename
    }
    __typename
  }
}
""",
            "variables": {
                "id": video_id
            }
        }).encode('utf-8')

        response = self._download_json(
            GRAPHQL_ENDPOINT, video_id, data=query,
            headers={"content-type": "application/json"})

        medium = try_get(response, lambda x: x['data']['medium'], dict)
        if not medium:
            raise ExtractorError('Unable to get video metadata')

        key = medium.get('key')
        if not key:
            raise ExtractorError('Unable to get video key')

        formats = self._extract_m3u8_formats(
            'https://storage.murrtube.net/murrtube/%s' % key, video_id)
        for f in formats:
            f['ext'] = 'mp4'
        self._sort_formats(formats)

        uploader = try_get(medium, lambda x: x['user']['slug'], compat_str)
        duration = int_or_none(medium.get('duration'))
        view_count = int_or_none(medium.get('viewsCount'))
        like_count = int_or_none(medium.get('likesCount'))
        comment_count = int_or_none(medium.get('commentsCount'))
        upload_date = unified_strdate(medium.get('publishedAt'))

        return {
            'id': video_id,
            'title': medium.get('title'),
            'description': medium.get('description'),
            'uploader': uploader,
            'upload_date': upload_date,
            'published_at': medium.get('publishedAt'),
            'duration': duration,
            'view_count': view_count,
            'like_count': like_count,
            'comment_count': comment_count,
            'tags': medium.get('tagList'),
            'formats': formats,
            'age_limit': 18,
            'ext': 'mp4'
        }


class MurrtubeUserVideosIE(InfoExtractor):
    _VALID_URL = _VALID_URL = r'https?://(?:www\.)?murrtube\.net/(?P<id>[^/]+)/videos'
    _TESTS = [{
        'url': 'https://murrtube.net/bayer/videos',
        'info_dict': {
            'id': 'bayer'
        },
        'playlist_mincount': 6
    }]

    def _real_extract(self, url):
        slug = self._match_id(url)

        query = json.dumps({
            "operationName": "User",
            "query": """query User($id: ID!) {
  user(id: $id) {
    id
    public
    chatEnabled
    slug
    name
    avatar
    banner
    bio
    website
    followed
    following
    mediaCount
    followersCount
    followingCount
    likesCount
    blocked
    __typename
  }
}
""",
            "variables": {
                "id": slug
            }
        }).encode('utf-8')

        response = self._download_json(
            GRAPHQL_ENDPOINT, slug, 'Downloading User ID', data=query,
            headers={"content-type": "application/json"})

        user_id = try_get(
            response, lambda x: x['data']['user']['id'], compat_str)
        if not user_id:
            raise ExtractorError('Unable to get User ID')

        videos = []
        for page_num in itertools.count():
            query = json.dumps({
                "operationName": "Media",
                "query": """query Media($q: String, $sort: String, $userId: ID, $offset: Int!, $limit: Int!) {
  media(q: $q, sort: $sort, userId: $userId, offset: $offset, limit: $limit) {
    id
    slug
    title
    description
    previewKey
    thumbnailKey
    smallThumbnailKey
    publishedAt
    duration
    commentsCount
    likesCount
    viewsCount
    tagList
    visibility
    restriction
    user {
      id
      slug
      name
      avatar
      __typename
    }
    __typename
  }
  users(q: $q, fillWithFollowing: false, offset: 0, limit: 2) {
    id
    slug
    name
    avatar
    mediaCount
    __typename
  }
}
""",
                "variables": {
                    "sort": "latest",
                    "userId": user_id,
                    "offset": page_num * 10,
                    "limit": 10
                }
            }).encode('utf-8')

            try:
                response = self._download_json(
                    GRAPHQL_ENDPOINT,
                    slug,
                    'Downloading page %d' % (page_num + 1),
                    data=query,
                    headers={"content-type": "application/json"}
                )
            except ExtractorError as e:
                if isinstance(e.cause, compat_HTTPError) and e.cause.code >= 400:
                    break
                raise

            media = try_get(response, lambda x: x['data']['media'], list)
            if not media or len(media) == 0:
                break

            for video in media:
                vid_slug = video.get('slug')
                vid_id = video.get('id')
                if not vid_slug and not vid_id:
                    continue
                videos.append(
                    self.url_result(
                        'https://murrtube.net/videos/%s-%s' % (vid_slug, vid_id),
                        MurrtubeIE.ie_key()))

        return self.playlist_result(videos, slug)
