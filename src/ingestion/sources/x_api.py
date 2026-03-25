# src/ingestion/sources/x_api.py
import logging

import tweepy

from src.shared.models import ContentItem

logger = logging.getLogger(__name__)


def ingest(source, since):
    client = tweepy.Client()
    username = source.url.rstrip("/").split("/")[-1]
    query = f"from:{username}"
    items = []
    next_token = None

    while True:
        kwargs = dict(
            query=query,
            start_time=since,
            tweet_fields=["created_at", "text"],
        )
        if next_token:
            kwargs["next_token"] = next_token

        try:
            response = client.search_recent_tweets(**kwargs)
        except tweepy.errors.TooManyRequests:
            logger.warning("rate limit hit mid-ingestion for source %s; returning partial results", source.id)
            break

        if response.data:
            for tweet in response.data:
                items.append(ContentItem(
                    id=str(tweet.id),
                    title=tweet.text,
                    source_id=source.id,
                    source_name=source.name,
                    published_date=tweet.created_at,
                    full_text=tweet.text,
                    original_url=f"https://twitter.com/i/web/status/{tweet.id}",
                ))

        # next_token must be a real string to continue pagination
        meta = getattr(response, "meta", None)
        token = getattr(meta, "next_token", None) if meta is not None else None
        if not isinstance(token, str) or not token:
            break
        next_token = token

    return items
