// harvest-watch-later.js -- read the Watch Later list from a logged-in YouTube tab.
//
// Load this file in the page (paste it, or evaluate it with the browser tool) on
// https://www.youtube.com/playlist?list=WL, then:
//
//   await harvestWatchLater()        -> { header, rendered, stable, items: [{id,title,channel,length}] }
//   harvestNow()                     -> items only, no scrolling (what is rendered right now)
//   verifyIds(["abc", "def"])        -> { present: [...], absent: [...] } from the rendered list
//
// harvestWatchLater scrolls until the rendered count has not changed for
// `settleRounds` consecutive rounds AND matches the header's video count, or
// until `maxRounds`. YouTube lazy-loads about 100 items per continuation and
// throttles timers in background tabs, so keep the tab in the foreground. A
// total that lands exactly on 100 or 200 is a lazy-load ceiling, not the list.
//
// Watch Later renders newest-added first. The order is preserved.
//
// Removal and "save to playlist" are done with the browser tool's clicks, not
// from here; this file only reads. Verify a removal with verifyIds after a
// reload; the header count lags for minutes and is not evidence.

function harvestNow() {
  return [...document.querySelectorAll("ytd-playlist-video-renderer")]
    .map((el) => {
      const a = el.querySelector("a#video-title");
      if (!a) return null;
      let id = null;
      try { id = new URL(a.href).searchParams.get("v"); } catch (e) { id = null; }
      return {
        id,
        title: a.textContent.trim(),
        channel: el.querySelector("ytd-channel-name a")?.textContent.trim() || "",
        length: el.querySelector("ytd-thumbnail-overlay-time-status-renderer")?.textContent.trim() || "",
      };
    })
    .filter((x) => x && x.id);
}

function headerCount() {
  // "487 videos" somewhere in the playlist header / sidebar stats
  const els = document.querySelectorAll(
    "yt-formatted-string, span.yt-core-attributed-string, .metadata-stats span, #stats yt-formatted-string"
  );
  for (const el of els) {
    const m = el.textContent.trim().match(/^([\d,]+)\s+videos?$/i);
    if (m) return parseInt(m[1].replace(/,/g, ""), 10);
  }
  return null;
}

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function harvestWatchLater({ waitMs = 1500, settleRounds = 5, maxRounds = 120 } = {}) {
  let last = -1, same = 0, rounds = 0, header = headerCount();
  while (rounds < maxRounds) {
    window.scrollTo(0, document.documentElement.scrollHeight);
    await sleep(waitMs);
    const n = document.querySelectorAll("ytd-playlist-video-renderer").length;
    header = headerCount() ?? header;
    same = n === last ? same + 1 : 0;
    last = n;
    rounds += 1;
    if (same >= settleRounds && (header === null || n >= header)) break;
  }
  const items = harvestNow();
  return {
    header,
    rendered: items.length,
    stable: same >= settleRounds && (header === null || items.length >= header),
    rounds,
    items,
  };
}

function verifyIds(ids) {
  const here = new Set(harvestNow().map((x) => x.id));
  return { present: ids.filter((i) => here.has(i)), absent: ids.filter((i) => !here.has(i)) };
}
