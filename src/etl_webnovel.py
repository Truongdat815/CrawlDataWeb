"""ETL demo: scrape a Webnovel book page (keys-only or small-chapter sample)

Usage:
  python src/etl_webnovel.py --book-url <book_url> --chapters 3

This script demonstrates extracting metadata, catalog (TOC), and a few
chapters, normalizing numeric/date values, and storing into MongoDB using a
simple schema compatible with the schema we designed.

Notes:
- This is a demo script for development/testing. For production use add
  retries, rate-limits, caching, and respect robots.txt/TOS.
"""

import re
import sys
import argparse
from urllib.parse import urljoin
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from pymongo import MongoClient
import os
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ETL-Demo/1.0)"
}


def parse_int(s):
    """Normalize strings like '1.4M', '137.8K', '2,721' to integer."""
    if s is None:
        return None
    s = str(s).strip()
    if s == "":
        return None
    # remove commas
    s = s.replace(",", "")
    m = re.match(r"^([0-9,.]+)\s*([KkMm])$", s)
    if m:
        num = float(m.group(1))
        unit = m.group(2).upper()
        if unit == "K":
            return int(num * 1_000)
        if unit == "M":
            return int(num * 1_000_000)
    try:
        return int(float(s))
    except Exception:
        return None


def text_or_none(el):
    return el.get_text(strip=True) if el else None


def fetch_book_metadata(book_url):
    r = requests.get(book_url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    title = text_or_none(soup.find("h1"))
    author_el = soup.select_one("a[href*='/profile/']")
    author = text_or_none(author_el)
    author_url = author_el['href'] if author_el and author_el.has_attr('href') else None

    cover = None
    cover_el = soup.select_one("img.book-cover, img[src*='bookcover']")
    if cover_el and cover_el.has_attr('src'):
        cover = cover_el['src']

    tags = [t.get_text(strip=True) for t in soup.select("a[href*='/tags/']")] or None

    # stats: views, chapters count, rating
    views = None
    chapters_count = None
    rating = None
    stats_text = soup.find(text=re.compile(r"Views|Chapters|Views", re.I))
    # best effort: find a chapters count label
    ch_el = soup.find(string=re.compile(r"\d+\s*Chapters|Chapters", re.I))
    if ch_el:
        m = re.search(r"(\d+[\d,\.]*)\s*Chapters", ch_el)
        if m:
            chapters_count = parse_int(m.group(1))

    # fallback: look for a small element near title
    meta = soup.select_one(".book-info .meta, .book-meta, .book-info")
    if meta:
        txt = meta.get_text(" ", strip=True)
        m = re.search(r"([\d,\.KMkm]+)\s*Views", txt)
        if m:
            views = parse_int(m.group(1))

    # badges and flags (ORIGINAL / PEAK / VIP hints)
    badges = [b.get_text(strip=True) for b in soup.select(".badge, .tag-badge")]

    # age rating
    age = None
    age_el = soup.find(text=re.compile(r"No One|Parental|Mature|R18|Parents", re.I))
    if age_el:
        age = age_el.strip()

    # gifts / power
    power = None
    power_el = soup.find(text=re.compile(r"Power|Powerstone|Power\s*stone|Power\s*stone", re.I))
    if power_el:
        m = re.search(r"([\d,\.KMkm]+)", power_el)
        if m:
            power = parse_int(m.group(1))

    # find catalog link (TOC)
    catalog_link = None
    toc = soup.find("a", href=re.compile(r"/catalog$|/catalog$|/book/\d+/catalog|/book/\d+/catalog"))
    if toc and toc.has_attr('href'):
        catalog_link = urljoin(book_url, toc['href'])
    else:
        # some pages use /book/<id>/catalog path referenced as '/book/<id>/catalog'
        match = re.search(r"/book/(\d+)", book_url)
        if match:
            catalog_link = f"https://www.webnovel.com/book/{match.group(1)}/catalog"

    # compose metadata
    meta_doc = {
        'source': 'webnovel',
        'url': book_url,
        'title': title,
        'author': {'name': author, 'url': author_url},
        'cover_url': cover,
        'tags': tags,
        'badges': badges,
        'age_rating': age,
        'views': views,
        'chapters_count': chapters_count,
        'power': power,
        'catalog_url': catalog_link,
    }

    # provenance and metadata for debugging
    meta_doc['_meta'] = {
        'scraped_at': datetime.utcnow().isoformat() + 'Z',
        'scraper': 'etl_webnovel.py',
        'scraper_version': '1.0',
    }
    return meta_doc


def fetch_catalog(catalog_url):
    # Webnovel uses a catalog page that returns a full HTML list of chapters; we scrape titles and chapter urls
    if not catalog_url:
        return []
    r = requests.get(catalog_url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    chapters = []
    for a in soup.select("a[href*='/book/']"):
        href = a.get('href')
        # ensure href is not None before evaluating other conditions
        if href and ('/chapter-' in href or '/read/' in href or re.search(r"/\d{6,}", href)):
            title = a.get_text(strip=True)
            chapters.append({'title': title, 'url': urljoin(catalog_url, href)})
    # de-duplicate while preserving order
    seen = set()
    out = []
    for c in chapters:
        if c['url'] not in seen:
            out.append(c)
            seen.add(c['url'])
    return out


def fetch_chapter(chapter_url):
    r = requests.get(chapter_url, headers=HEADERS, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    title = text_or_none(soup.find("h1"))
    # content paragraphs
    paras = [p.get_text("\n", strip=True) for p in soup.select('.cha-words, .chapter-content, .read-content p')]
    content = "\n\n".join([p for p in paras if p])
    # check paywall hints (common markers: 'VIP', 'Unlock', 'Paid')
    is_paid = bool(soup.find(string=re.compile(r"VIP|Unlock|Paid|coin", re.I)))
    # coin price extraction
    coin_price = None
    coin_el = soup.find(string=re.compile(r"\d+\s*coins|coin(s)?|price", re.I))
    if coin_el:
        m = re.search(r"(\d+[\d,\.]*)", coin_el)
        if m:
            coin_price = parse_int(m.group(1))

    # Extract canonical chapter id if present in URL (Webnovel often uses long numeric IDs)
    chapter_id = None
    try:
        m = re.search(r"(\d{6,})", chapter_url)
        if m:
            chapter_id = m.group(1)
    except Exception:
        chapter_id = None

    return {
        'url': chapter_url,
        'chapter_id': chapter_id,
        'title': title,
        'content': content,
        'is_paid': is_paid,
        'coin_price': coin_price,
    }


def store_to_mongo(meta_doc, chapters_docs, mongo_uri='mongodb://localhost:27017', dbname='webnovel_demo'):
    client = MongoClient(mongo_uri)
    db = client[dbname]
    fictions = db.fictions
    chapters = db.chapters
    # upsert fiction
    fiction_id = fictions.update_one({'url': meta_doc['url']}, {'$set': meta_doc}, upsert=True).upserted_id
    # store chapters
    for ch in chapters_docs:
        ch_doc = ch.copy()
        ch_doc['fiction_url'] = meta_doc['url']
        chapters.update_one({'url': ch_doc['url']}, {'$set': ch_doc}, upsert=True)
    print('Stored metadata and', len(chapters_docs), 'chapters to MongoDB')


def _book_id_from_url(book_url):
    """Extract numeric book id from typical Webnovel URL suffix *_<id>"""
    try:
        m = re.search(r"_?(\d{6,})$", book_url)
        if m:
            return m.group(1)
        # fallback: search any 6+ digit sequence
        m = re.search(r"(\d{6,})", book_url)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def _safe_slug(text):
    if not text:
        return 'unknown'
    s = re.sub(r'[^0-9a-zA-Z\-]+', '_', text)
    s = re.sub(r'_+', '_', s).strip('_')
    return s[:120]


def save_json(meta_doc, chapters_docs, out_dir='data/json'):
    os.makedirs(out_dir, exist_ok=True)
    book_id = _book_id_from_url(meta_doc.get('url', '')) or 'unknown'
    title_slug = _safe_slug(meta_doc.get('title') or meta_doc.get('url') or book_id)
    filename = f"{book_id}_{title_slug}.json"
    path = os.path.join(out_dir, filename)

    out = {
        'meta': meta_doc,
        'chapters': chapters_docs,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print('Saved JSON to', path)
    return path


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--book-url', required=True)
    p.add_argument('--chapters', type=int, default=3, help='Number of chapters to fetch (sample)')
    p.add_argument('--mongo', default='mongodb://localhost:27017')
    p.add_argument('--output', choices=['json', 'mongo'], default='json', help='Output: save json file or upsert to mongo')
    p.add_argument('--download-cover', choices=['yes','no'], default='no', help='Download cover image (yes/no)')
    args = p.parse_args()

    meta = fetch_book_metadata(args.book_url)
    print('Title:', meta.get('title'))
    print('Author:', meta.get('author'))
    print('Catalog:', meta.get('catalog_url'))

    catalog = fetch_catalog(meta.get('catalog_url'))
    print('Catalog entries found (sample):', len(catalog))
    chapters_to_get = catalog[:args.chapters]
    chapters_docs = []
    for ch in chapters_to_get:
        try:
            ch_doc = fetch_chapter(ch['url'])
            # keep only small sample content when demo-ing
            chapters_docs.append({
                'url': ch_doc['url'],
                'title': ch_doc['title'],
                'is_paid': ch_doc['is_paid'],
                'coin_price': ch_doc['coin_price'],
            })
        except Exception as e:
            print('Failed fetch chapter', ch.get('url'), e)

    if args.output == 'mongo':
        store_to_mongo(meta, chapters_docs, mongo_uri=args.mongo)
    else:
        # Save to JSON file in data/json
        json_path = save_json(meta, chapters_docs)
        print('Wrote sample JSON to', json_path)


if __name__ == '__main__':
    main()
