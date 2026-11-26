"""Fetch the Blu Breeze blog feed from Shopify (theme template /blogs/blog?view=rss, which
includes each post's featured image; Shopify's own .atom feed does not) and publish it as a clean RSS 2.0 file
that Pinterest auto-publish can read. Runs in GitHub Actions; no secrets needed."""
import email.utils, html, re, sys, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime

SITE = "https://blubreezecreations.com"
ATOM = SITE + "/blogs/blog.atom"
OUT = sys.argv[1] if len(sys.argv) > 1 else "public/feed.xml"
A = "{http://www.w3.org/2005/Atom}"
def esc(s): return html.escape(s or "", quote=True)
def text(html_s):
    t = re.sub(r"<[^>]+>", " ", html.unescape(html_s or ""))
    return re.sub(r"\s+", " ", t).strip()

SRC = SITE + "/blogs/blog?view=rss"
def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (BluBreezeFeedBot)"})
    return urllib.request.urlopen(r, timeout=30).read()

def from_theme_rss():
    rss = ET.fromstring(get(SRC).strip())
    out = []
    M = "{http://search.yahoo.com/mrss/}"
    for it in rss.iter("item"):
        mc = it.find(M + "content")
        if mc is None: continue
        link = re.sub(r"^https?://[^/]+", SITE, it.findtext("link").strip())
        out.append(dict(title=it.findtext("title"), link=link, pub=it.findtext("pubDate"),
                        desc=it.findtext("description"), img=mc.get("url")))
    return out

try:
    theme_items = from_theme_rss()
except Exception as ex:
    print("Theme RSS unavailable:", ex); theme_items = []

items = []
for t in theme_items:
    items.append(f"""    <item>
      <title>{esc(t['title'])}</title>
      <link>{esc(t['link'])}</link>
      <guid isPermaLink="true">{esc(t['link'])}</guid>
      <pubDate>{esc(t['pub'])}</pubDate>
      <description>{esc(t['desc'])}</description>
      <media:content url="{esc(t['img'])}" medium="image"/>
      <enclosure url="{esc(t['img'])}" type="image/jpeg" length="0"/>
    </item>""")

req = urllib.request.Request(ATOM, headers={"User-Agent": "Mozilla/5.0 (BluBreezeFeedBot)"})
root = ET.fromstring(urllib.request.urlopen(req, timeout=30).read()) if not items else ET.Element("x")


for e in root.findall(A + "entry"):
    link = next((l.get("href") for l in e.findall(A + "link") if l.get("rel", "alternate") == "alternate"), None)
    if not link: continue
    link = re.sub(r"^https?://[^/]+", SITE, link)  # always the claimed domain
    content = (e.findtext(A + "content") or "") + (e.findtext(A + "summary") or "")
    img = re.search(r'<img[^>]+src="([^"]+)"', html.unescape(content))
    if not img:
        continue  # Pinterest needs an image; skip posts without one
    src = img.group(1)
    src = "https:" + src if src.startswith("//") else src
    pub = e.findtext(A + "published") or e.findtext(A + "updated")
    dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
    summary = text(e.findtext(A + "summary")) or text(e.findtext(A + "content"))
    words = summary.split()
    desc = " ".join(words[:60]) + ("…" if len(words) > 60 else "")
    items.append(f"""    <item>
      <title>{esc(e.findtext(A + 'title'))}</title>
      <link>{esc(link)}</link>
      <guid isPermaLink="true">{esc(link)}</guid>
      <pubDate>{email.utils.format_datetime(dt)}</pubDate>
      <description>{esc(desc)}</description>
      <media:content url="{esc(src)}" medium="image"/>
      <enclosure url="{esc(src)}" type="image/jpeg" length="0"/>
    </item>""")

if not items:
    sys.exit("No posts with images found; keeping the previous feed.")

xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Blog | Blu Breeze Creations</title>
    <link>{SITE}/blogs/blog</link>
    <description>How-tos, ideas and inspiration from Blu Breeze Creations.</description>
    <language>en</language>
{chr(10).join(items)}
  </channel>
</rss>
"""
ET.fromstring(xml.encode())  # validate
import os; os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(xml)
print(f"Wrote {len(items)} items to {OUT}")
