# src/ingestion/sources/x_api.py
import tweepy

from src.shared.models import ContentItem


def ingest(source, since):
    client = tweepy.Client()
    query = f"from:{source.url.rstrip('/').split('/')[-1]}"
    start_time = since
    response = client.search_recent_tweets(
        query=query,
        start_time=start_time,
        tweet_fields=["created_at", "text"],
    )
    items = []
    if not response.data:
        return items
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
    return items
