"""
IMS NSIT Class Timetable Scraper  (constraint-driven edition)
─────────────────────────────────────────────────────────────
Changes from the brute-force version
────────────────────────────────────
• Traversal order is now:  sem → section → degree → dept → spec
  (degree drives the outer loop; impossible combinations are filtered
   BEFORE any network request is made)
• heuristics.py supplies:
    - Static constraint maps    (DEGREE_TO_DEPARTMENTS, etc.)
    - Fuzzy string normalisation
    - HeuristicsCache           (auto-learns from successful scrapes)
    - Blacklist                 (prunes dept×degree after 3 failures)
• filter_depts_for_degree() and filter_specs_for_dept() are called
  each iteration to skip impossible combos.
• On every successful timetable save the cache is updated + written.
• Resume support preserved (file-existence check unchanged).
"""

import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import re

# ── Import constraint helpers ────────────────────────────────────────────────
from heuristics import (
    HeuristicsCache,
    Blacklist,
    filter_depts_for_degree,
    filter_specs_for_dept,
    normalize,
    match_degree,
)

load_dotenv()


# ─────────────────────────────────────────────────────────────────────────────
# Utility
# ─────────────────────────────────────────────────────────────────────────────

def safe_filename(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', '_', str(text)).strip('_')


# ─────────────────────────────────────────────────────────────────────────────
# Scraper
# ─────────────────────────────────────────────────────────────────────────────

class ClassTimetableScraper:

    def __init__(self, user_id=None, password=None, fin_year="2025-26"):
        self.user_id  = user_id  or os.getenv("IMS_USER_ID")
        self.password = password or os.getenv("IMS_PASSWORD")
        self.fin_year = fin_year
        self.base_url = "https://www.imsnsit.org/imsnsit/"

        self.target_sems     = [2, 4, 6, 8]
        self.target_sections = [1, 2, 3]

        # Degrees to skip entirely — add/remove normalised keys as needed.
        # Uses the same normalize() from heuristics so "B.E." / "BE" both match.
        self.skip_degrees: set[str] = {
            "BE",
            "BACHELOR OF ENGINEERING",
        }

        self.output_dir = os.path.expanduser("~/ims_scraper_outputs/classes")
        os.makedirs(self.output_dir, exist_ok=True)

        # Heuristic helpers (shared across the whole run)
        self.cache     = HeuristicsCache()
        self.blacklist = Blacklist(persist_threshold=3, skip_threshold=6)

        # Maps logical key → actual HTML name attribute (filled by _discover_select_names)
        self.sel = {
            "sem":     None,
            "section": None,
            "dept":    None,
            "degree":  None,
            "spec":    None,
            "day":     None,
        }

    # ── Anti-debugger bypass ─────────────────────────────────────────────────
    async def _bypass(self, page):
        try:
            await page.evaluate("""
                window.debugger = () => {};
                const _si = window.setInterval;
                window.setInterval = function(cb, d, ...a) {
                    if (cb && typeof cb === 'function') {
                        const s = cb.toString();
                        if (/debugger|dbg|OffFF|d\\s*=\\s*new\\s+Date/i.test(s)) return -1;
                    }
                    return _si(cb, d, ...a);
                };
                for (let i = 0; i < 10000; i++) { try { clearInterval(i); } catch(e) {} }
                const _st = window.setTimeout;
                window.setTimeout = function(cb, d, ...a) {
                    if (cb && typeof cb === 'function' && /debugger|dbg/i.test(cb.toString())) return -1;
                    return _st(cb, d, ...a);
                };
            """)
        except Exception:
            pass

    # ── Login ────────────────────────────────────────────────────────────────
    async def login(self, page) -> bool:
        print("🌐  Loading IMS portal…")
        await page.goto(self.base_url, wait_until="domcontentloaded")
        await self._bypass(page)
        await page.wait_for_timeout(1000)

        print("🎓  Clicking Student Login…")
        try:
            login_btn_selector = 'input[value="Student Login"]'
            await page.wait_for_selector(login_btn_selector, state='visible', timeout=5000)
            await page.click(login_btn_selector)
        except Exception:
            await page.click('text="Student Login"')

        await page.wait_for_load_state('domcontentloaded')
        await self._bypass(page)

        print("🖼️   Waiting for login frame…")
        frame = None
        try:
            element_handle = await page.wait_for_selector('frame[name="banner"]', timeout=3000)
            frame = await element_handle.content_frame()
        except Exception:
            frame = page.frame(name="banner")
        if not frame:
            frame = page

        print(f"📝  Entering credentials for {self.user_id}…")
        try:
            await frame.wait_for_selector('input[name="txtuserid"]', timeout=3000)
            await frame.fill('input[name="txtuserid"]', self.user_id)
        except Exception:
            await frame.fill('input[placeholder="Enter userid"]', self.user_id)

        try:
            await frame.fill('input[name="txtpassword"]', self.password)
        except Exception:
            await frame.fill('input[placeholder="Enter password"]', self.password)

        try:
            await frame.select_option('select[name="cmbfinyear"]', self.fin_year)
        except Exception:
            pass

        print("\n" + "=" * 60)
        print("⏳  Solve the captcha in the browser, then press ENTER here…")
        print("=" * 60 + "\n")
        await asyncio.get_event_loop().run_in_executor(None, input)

        print("🔐  Logging in…")
        try:
            await frame.click('input[value="Login"]')
        except Exception:
            await frame.click('input[type="submit"]')

        await page.wait_for_load_state('networkidle', timeout=30000)
        await self._bypass(page)

        for ctx in [page] + list(page.frames):
            try:
                if await ctx.query_selector("text=/Welcome/i"):
                    print("✅  Login successful!\n")
                    return True
            except Exception:
                pass

        print("⚠️   Welcome text not found — continuing anyway.\n")
        return False

    # ── Navigate to ClassTimetable ───────────────────────────────────────────
    async def navigate_to_class_timetable(self, page):
        print("=" * 60)
        print("📍  Go to: TIME TABLE → ClassTimetable in the browser.")
        print("    Wait for the form with dropdowns to appear.")
        print("    Then press ENTER here…")
        print("=" * 60 + "\n")
        await asyncio.get_event_loop().run_in_executor(None, input)
        await self._bypass(page)

    # ── Find the frame hosting the timetable form ────────────────────────────
    async def _find_form_frame(self, page):
        all_frames = list(page.frames)

        def collect_child_frames(frame):
            for child in frame.child_frames:
                all_frames.append(child)
                collect_child_frames(child)

        for f in list(page.frames):
            collect_child_frames(f)

        best_frame = None
        best_count = 0

        for ctx in all_frames:
            try:
                count = await ctx.evaluate(
                    "() => document.querySelectorAll('select').length"
                )
                print(f"   Frame '{getattr(ctx,'name','?')}' ({ctx.url[:60]}) → {count} selects")
                if count > best_count:
                    best_count = count
                    best_frame = ctx
            except Exception:
                pass

        return best_frame

    # ── Auto-discover select names ───────────────────────────────────────────
    async def _discover_select_names(self, frame):
        raw = await frame.evaluate("""
            () => {
                const out = [];
                document.querySelectorAll('select').forEach(s => {
                    const opts = Array.from(s.options).map(o => o.text.trim()).slice(0,5);
                    out.push({ name: s.name || '', id: s.id || '', options: opts });
                });
                return out;
            }
        """)

        print("\n📋  Selects found on page:")
        for s in raw:
            print(f"      name='{s['name']}' id='{s['id']}' | first opts: {s['options']}")

        patterns = {
            "sem":     re.compile(r'sem(ester)?',                   re.I),
            "section": re.compile(r'sec(tion)?',                    re.I),
            "dept":    re.compile(r'dep(t|artment)?|subdepartment', re.I),
            "degree":  re.compile(r'deg(ree)?|program',             re.I),
            "spec":    re.compile(r'spec(iali[sz]ation)?|branch',   re.I),
            "day":     re.compile(r'day|wkd',                       re.I),
        }

        for s in raw:
            identifier = (s["name"] + " " + s["id"]).strip()
            for key, pat in patterns.items():
                if self.sel[key] is None and pat.search(identifier):
                    self.sel[key] = s["name"] or s["id"]
                    print(f"      ✅  Mapped '{key}' → select name='{self.sel[key]}'")
                    break

        for key, val in self.sel.items():
            if val is None:
                print(f"      ⚠️  Could not auto-map '{key}' — will skip that filter.")
        print()

    # ── Read live options from a discovered select ───────────────────────────
    async def _get_options(self, frame, logical_key: str) -> list:
        name = self.sel.get(logical_key)
        if not name:
            return []
        try:
            opts = await frame.evaluate(f"""
                () => {{
                    const sel = document.querySelector('select[name="{name}"]')
                              || document.querySelector('select[id="{name}"]');
                    if (!sel) return [];
                    return Array.from(sel.options).map(o => ({{
                        value: o.value.trim(),
                        text:  o.text.trim()
                    }}));
                }}
            """)
            return [o for o in opts if o["value"].strip()]
        except Exception:
            return []

    # ── Select one value ─────────────────────────────────────────────────────
    async def _select(self, frame, logical_key: str, value: str, wait_ms: int = 500):
        name = self.sel.get(logical_key)
        if not name:
            return
        selector = f'select[name="{name}"]'

        selected_value = value
        if value.lower() == 'all':
            try:
                opts = await self._get_options(frame, logical_key)
                all_opt = next((o for o in opts if o['text'].lower() == 'all'), None)
                if all_opt:
                    selected_value = all_opt['value']
            except Exception:
                pass

        try:
            await frame.select_option(selector, selected_value)
            if wait_ms > 0:
                await frame.wait_for_timeout(wait_ms)
        except Exception as e:
            print(f"            ⚠️  select({logical_key}={selected_value}): {e}")

    # ── Click Go, poll all frames for timetable ──────────────────────────────
    async def _click_go_and_wait(self, page, form_frame, timeout_s: int = 15):
        """
        Click the Go button exactly the way the working room scraper does:
          1. Stamp a sentinel on the DOM so we can detect a genuine refresh.
          2. Find Go with the two selectors that are known to work on IMS.
          3. Plain await el.click() — no JS fallback, no try/except swallowing.
          4. Poll every live page frame for the T1/T2 result table.

        Returns (True, result_frame) on success, (False, None) on timeout.
        """
        # ── Step 1: stamp a sentinel value so we know when DOM has refreshed ─
        # This is the same trick the room scraper uses to avoid reading stale data.
        try:
            await form_frame.evaluate("""
                () => {
                    // Mark any existing timetable tables as stale
                    document.querySelectorAll('table').forEach(t => {
                        if ((t.innerText || '').includes('T1'))
                            t.setAttribute('data-stale', '1');
                    });
                }
            """)
        except Exception:
            pass

        # ── Step 2: find Go button — same two selectors the room scraper uses ─
        go_btn = (
            await form_frame.query_selector('input[value="Go"]')
            or await form_frame.query_selector('input[type="submit"]')
        )
        if not go_btn:
            print("            ⚠️  Go button not found in form frame.")
            return False, None

        val = await go_btn.get_attribute("value") or "(no value)"
        print(f"            🖱️   Clicking Go  [{val}]")

        # ── Step 3: plain Playwright click — identical to room scraper ─────────
        await go_btn.click()

        # ── Step 4: poll all live frames for a fresh (non-stale) T1/T2 table ──
        _FRESH_TABLE_JS = """
            () => {
                for (const t of document.querySelectorAll('table')) {
                    if (t.getAttribute('data-stale') === '1') continue;  // skip old table
                    const txt = t.innerText || '';
                    if (txt.includes('T1') && txt.includes('T2')
                        && t.querySelectorAll('tr').length > 3)
                        return true;
                }
                return false;
            }
        """

        def _all_frames():
            seen, stack = [], list(page.frames)
            while stack:
                f = stack.pop()
                if f not in seen:
                    seen.append(f)
                    stack.extend(f.child_frames)
            return seen

        for elapsed in range(timeout_s):
            await asyncio.sleep(1)
            for f in _all_frames():
                try:
                    if await f.evaluate(_FRESH_TABLE_JS):
                        print(f"            ✅  Table found in frame "
                              f"'{getattr(f, 'name', '?')}' after {elapsed+1}s")
                        return True, f
                except Exception:
                    pass  # frame mid-navigation — try next iteration

        print(f"            ⏱️  Timed out after {timeout_s}s — no timetable table found.")
        return False, None

    async def _parse_timetable(self, frame) -> dict:
        return await frame.evaluate("""
            () => {
                const result = {};
                const dayNames = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

                const tables = Array.from(document.querySelectorAll('table'));
                
                for (let table of tables) {
                    const fullText = table.innerText || '';
                    if (!fullText.includes('T1') && !fullText.includes('T 1') && !fullText.includes('T2')) continue;

                    const rows = Array.from(table.querySelectorAll('tr'));
                    let headerRowIndices = [];
                    
                    for (let i = 0; i < rows.length; i++) {
                        const row = rows[i];
                        const cells = Array.from(row.querySelectorAll('td,th'));
                        const texts = cells.map(c => c.innerText.trim());
                        if (texts.some(t => /^T\\s*\\d+/.test(t) || t === 'T1' || t === 'T 1' || t.includes('T1') || t.includes('T2'))) {
                            if (texts.length > 2) {
                                headerRowIndices.push(i);
                            }
                        }
                    }
                    
                    for (let h = 0; h < headerRowIndices.length; h++) {
                        const hIdx = headerRowIndices[h];
                        const headerRow = rows[hIdx];
                        const nextHIdx = (h + 1 < headerRowIndices.length) ? headerRowIndices[h + 1] : rows.length;
                        
                        let label = 'CORE';
                        for (let back = hIdx - 1; back >= 0; back--) {
                            if (h > 0 && back <= (headerRowIndices[h-1] || -1)) break;
                            const txt = rows[back].innerText.trim();
                            if (txt.includes('Time Table')) {
                                const m = txt.match(/Time Table\\s*\\(([^)]+)\\)/i);
                                label = m ? m[1].trim() : txt.slice(0,40).replace(/\\s+/g,' ');
                                break;
                            }
                        }
                        if (result[label]) {
                            label += '_' + h;
                        }
                        
                        const cells = Array.from(headerRow.querySelectorAll('td,th'));
                        const texts = cells.map(c => c.innerText.trim());
                        
                        let slotMeta = [];
                        for (let j = 1; j < texts.length; j++) {
                            const parts = texts[j].split(/[\\n\\r]+/);
                            const slot = parts[0].trim();
                            const time_range = parts.length > 1 ? parts.slice(1).join(' ').trim() : null;
                            slotMeta.push({ slot, time_range });
                        }
                        
                        let blockStart = hIdx + 1;
                        if (blockStart < nextHIdx && slotMeta.every(s => !s.time_range)) {
                            const nxtCells = Array.from(rows[blockStart].querySelectorAll('td,th'))
                                            .map(c => c.innerText.trim());
                            if (nxtCells.some(t => t.includes(':'))) {
                                for(let j = 1; j < nxtCells.length && (j-1) < slotMeta.length; j++) {
                                    slotMeta[j-1].time_range = nxtCells[j];
                                }
                                blockStart++;
                            }
                        }
                        
                        const schedule = {};
                        const legend = [];
                        let pastLastDay = false;
                        
                        for (let i = blockStart; i < nextHIdx; i++) {
                            const row = rows[i];
                            const rCells = Array.from(row.querySelectorAll('td,th'));
                            if (!rCells.length) continue;
                            const first = rCells[0].innerText.trim();
                            
                            if (pastLastDay) {
                                const txt = row.innerText.trim().replace(/\\s+/g,' ');
                                if (txt.includes(' - ') && txt.includes('/')) legend.push(txt);
                                continue;
                            }
                            
                            if (!dayNames.some(d => first.startsWith(d))) {
                                continue;
                            }
                            
                            if (first.startsWith('Sat') || first.startsWith('Sun')) pastLastDay = true;
                            
                            schedule[first] = [];
                            for (let j = 1; j < rCells.length && (j-1) < slotMeta.length; j++) {
                                const content = (rCells[j] ? rCells[j].innerText.trim().replace(/\\s+/g,' ') : '');
                                schedule[first].push({
                                    slot: slotMeta[j-1].slot,
                                    time_range: slotMeta[j-1].time_range,
                                    content,
                                    is_free: content.length <= 2
                                });
                            }
                        }
                        
                        if (Object.keys(schedule).length > 0) {
                            result[label] = { time_slots: slotMeta, schedule, legend };
                        }
                    }
                }
                return result;
            }
        """)

    # ── Output path + save ───────────────────────────────────────────────────
    def _output_path(self, sem, section, dept, degree, spec) -> str:
        fname = safe_filename(f"Sem{sem}_Sec{section}_{dept}_{degree}_{spec}") + ".json"
        return os.path.join(self.output_dir, fname)

    def _save(self, record: dict):
        path = self._output_path(
            record["semester"], record["section"],
            record["department"], record["degree"], record["spec"]
        )
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        print(f"            💾  {os.path.basename(path)}")

    # ─────────────────────────────────────────────────────────────────────────
    # Main constraint-driven loop
    # ─────────────────────────────────────────────────────────────────────────
    async def _scrape_all(self, page, frame):
        """
        Traversal order:  sem → section → degree → dept → spec
        Filtering:
          • degree_opts   — full live list (no filter; degree is the anchor)
          • dept_opts     — filtered via filter_depts_for_degree()
          • spec_opts     — filtered via filter_specs_for_dept()
        Learning:
          • On success → cache.record_success() + blacklist.record_success()
          • On failure → blacklist.record_failure()
          • Cache saved every 10 successes (and always at the end)
        """
        stats = {
            "total": 0, "saved": 0, "empty": 0,
            "skipped": 0, "pruned_dept": 0, "pruned_spec": 0,
        }
        save_counter = 0

        for sem in self.target_sems:
            print(f"\n{'='*60}\n📅  Semester {sem}\n{'='*60}")

            # Prime the degree dropdown for this semester
            await self._select(frame, "sem", str(sem), wait_ms=800)
            degree_opts = await self._get_options(frame, "degree")

            if not degree_opts:
                print(f"   ⚠️  No degrees found for sem={sem}.")
                continue

            print(f"   Degrees ({len(degree_opts)}): {[o['text'] for o in degree_opts]}")

            for section in self.target_sections:
                print(f"\n   🗂️  Section {section}")

                for degree in degree_opts:
                    # ── Skip degrees configured in self.skip_degrees ──────────
                    # Use match_degree() so "B.E. (Full Time)" → "BE" etc.
                    deg_key = match_degree(degree["text"]) or normalize(degree["text"])
                    if deg_key in self.skip_degrees:
                        print(f"\n      ⏭️   Skipping degree: {degree['text']}  (in skip list)")
                        continue

                    print(f"\n      🎓  Degree: {degree['text']}")

                    # ── Get full dept list for this sem+degree ─────────────
                    await self._select(frame, "sem",    str(sem),         wait_ms=400)
                    await self._select(frame, "degree", degree["value"],  wait_ms=600)
                    raw_dept_opts = await self._get_options(frame, "dept")

                    if not raw_dept_opts:
                        print(f"         ⚠️  No departments — skipping degree.")
                        continue

                    # ── Apply heuristic dept filter ────────────────────────
                    dept_opts = filter_depts_for_degree(
                        raw_dept_opts, degree["text"], self.cache
                    )
                    pruned_d = len(raw_dept_opts) - len(dept_opts)
                    if pruned_d:
                        stats["pruned_dept"] += pruned_d
                        print(f"         ✂️   Dept filter: {len(raw_dept_opts)} → {len(dept_opts)} "
                              f"({pruned_d} pruned)")
                    print(f"         Departments: {[o['text'] for o in dept_opts]}")

                    for dept in dept_opts:
                        # Skip entire dept×degree pair if blacklisted
                        if self.blacklist.is_blacklisted(dept["text"], degree["text"]):
                            print(f"            🚫  Skipping blacklisted: "
                                  f"{dept['text']} × {degree['text']}")
                            continue

                        print(f"\n         🏛️  Dept: {dept['text']}")

                        # ── Seed spec dropdown ─────────────────────────────
                        await self._select(frame, "sem",    str(sem),         wait_ms=300)
                        await self._select(frame, "degree", degree["value"],  wait_ms=400)
                        await self._select(frame, "dept",   dept["value"],    wait_ms=600)
                        raw_spec_opts = await self._get_options(frame, "spec")

                        # Treat "no specs" as a single N/A placeholder
                        if not raw_spec_opts:
                            raw_spec_opts = [{"value": "", "text": "N_A"}]

                        # ── Apply heuristic spec filter ────────────────────
                        spec_opts = filter_specs_for_dept(
                            raw_spec_opts, dept["text"], self.cache
                        )
                        pruned_s = len(raw_spec_opts) - len(spec_opts)
                        if pruned_s:
                            stats["pruned_spec"] += pruned_s
                            print(f"            ✂️   Spec filter: {len(raw_spec_opts)} → {len(spec_opts)} "
                                  f"({pruned_s} pruned)")
                        else:
                            print(f"            Specs: {[o['text'] for o in spec_opts]}")

                        for spec in spec_opts:
                            stats["total"] += 1
                            tag = (f"Sem{sem} Sec{section} | "
                                   f"{dept['text']} / {degree['text']} / {spec['text']}")

                            # Resume support
                            if os.path.exists(self._output_path(
                                    sem, section,
                                    dept["text"], degree["text"], spec["text"])):
                                print(f"            ⏭️  Cached: {tag}")
                                stats["skipped"] += 1
                                continue

                            print(f"            🔄  {tag}")

                            # ── Full explicit selection ────────────────────
                            await self._select(frame, "sem",     str(sem),         wait_ms=400)
                            await self._select(frame, "section", str(section),     wait_ms=300)
                            await self._select(frame, "degree",  degree["value"],  wait_ms=400)
                            await self._select(frame, "dept",    dept["value"],    wait_ms=500)
                            if spec["value"]:
                                await self._select(frame, "spec", spec["value"],   wait_ms=400)
                            await self._select(frame, "day", "All", wait_ms=150)

                            # ── Go ─────────────────────────────────────────
                            loaded, result_frame = await self._click_go_and_wait(
                                page, frame, timeout_s=15
                            )

                            if not loaded:
                                print(f"            ⚠️  No timetable loaded.")
                                stats["empty"] += 1
                                if self.blacklist.record_failure(dept["text"], degree["text"]):
                                    break   # ← stop remaining specs for this dept immediately
                                continue

                            await self._bypass(page)
                            # Parse from whichever frame the table appeared in
                            timetable = await self._parse_timetable(result_frame)

                            if not timetable:
                                print(f"            ⚠️  Parser found nothing.")
                                stats["empty"] += 1
                                if self.blacklist.record_failure(dept["text"], degree["text"]):
                                    break   # ← stop remaining specs for this dept immediately
                                continue

                            # ── Success ────────────────────────────────────
                            self._save({
                                "scraped_at": datetime.now().isoformat(),
                                "fin_year":   self.fin_year,
                                "semester":   sem,
                                "section":    section,
                                "department": dept["text"],
                                "degree":     degree["text"],
                                "spec":       spec["text"],
                                "timetable":  timetable,
                            })
                            stats["saved"] += 1
                            save_counter  += 1

                            # Update heuristics
                            self.cache.record_success(
                                dept["text"], degree["text"], spec["text"]
                            )
                            self.blacklist.record_success(dept["text"], degree["text"])

                            # Periodic cache flush (every 10 successes)
                            if save_counter % 10 == 0:
                                self.cache.save()

                            await page.wait_for_timeout(200)

        return stats

    # ── Public entry point ───────────────────────────────────────────────────
    async def run(self, headless=False):
        print("\n" + "=" * 60)
        print("🚀  IMS CLASS TIMETABLE SCRAPER  (constraint-driven)")
        print("=" * 60 + "\n")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                    "--no-sandbox",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            await context.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            )
            page = await context.new_page()

            try:
                await self.login(page)
                await self.navigate_to_class_timetable(page)

                print("🔍  Scanning all frames for select elements…")
                frame = await self._find_form_frame(page)
                if not frame:
                    print("❌  No frame with selects found. Did you navigate correctly?")
                    return
                print(f"✅  Using frame: '{getattr(frame,'name','(main)')}'\n")

                await self._discover_select_names(frame)

                if self.sel["sem"] is None or self.sel["degree"] is None:
                    print("❌  Cannot find sem or degree dropdown. Exiting.")
                    return

                stats = await self._scrape_all(page, frame)

                # Final cache flush
                self.cache.save(force=True)

                # ── Summary ──────────────────────────────────────────────
                print("\n" + "=" * 60)
                print("📊  DONE")
                print(f"    Combinations attempted : {stats['total']}")
                print(f"    Saved                  : {stats['saved']}")
                print(f"    Empty / no timetable   : {stats['empty']}")
                print(f"    Resumed from cache     : {stats['skipped']}")
                print(f"    Dept combos pruned     : {stats['pruned_dept']}")
                print(f"    Spec combos pruned     : {stats['pruned_spec']}")
                total_pruned = stats["pruned_dept"] + stats["pruned_spec"]
                total_attempted = stats["total"] + total_pruned
                if total_attempted:
                    pct = 100 * total_pruned / total_attempted
                    print(f"    Reduction              : {pct:.1f}%  "
                          f"({total_pruned} of {total_attempted} skipped before request)")
                print(f"    Output dir             : {self.output_dir}")
                print(f"    Heuristics cache       : {self.cache.path}")
                print("=" * 60 + "\n")

            except Exception as e:
                print(f"\n❌  FATAL: {e}")
                import traceback
                traceback.print_exc()
                self.cache.save(force=True)   # Always persist learning on crash
            finally:
                if not headless:
                    print("🔍  Browser open. Close window or Ctrl+C to exit.")
                    await page.pause()
                else:
                    await browser.close()


# ─────────────────────────────────────────────────────────────────────────────

async def main():
    scraper = ClassTimetableScraper(
        user_id="2022UIT3042",
        password="vogsue-7",
        fin_year="2025-26",
    )
    await scraper.run(headless=False)


if __name__ == "__main__":
    asyncio.run(main())