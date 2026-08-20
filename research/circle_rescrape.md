# Circle re-scrape

Re-scraped Circle spaces via the authenticated `internal_api` the Circle web app uses, driven through the same logged-in Chrome CDP session (port 9222) the existing `circle_scraper.py` uses — no new auth path. Each post now carries `created_at`, `author`, `post_id`, `space` alongside the existing `text` and `images`. Video/audio out of scope.

## counts

```
spaces_rescraped: 6
posts_with_ts: 380
posts_with_author: 380
posts_total: 380
span_utc: 2024-12-08 -> 2026-08-20
```

## per-space

| space | posts_with_ts | posts_with_author |
|---|---|---|
| a-setups | 215 | 215 |
| important-info | 26 | 26 |
| key-levels | 78 | 78 |
| resources | 57 | 57 |
| traders-lab-chat | 0 | 0 |
| announcements | 4 | 4 |

Note: the prior `posts.json` counts (a-setups 649, important-info 107, key-levels 77, resources 57, traders-lab-chat 49, announcements 33) were DOM-scraped and over-counted comments as posts. The `internal_api/spaces/{id}/posts` endpoint returns top-level posts only, so `posts_v2.json` counts are lower and accurate. traders-lab-chat is a chat space (posts_count=0) — no top-level posts via the posts API.

