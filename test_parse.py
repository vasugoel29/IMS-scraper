import asyncio
from playwright.async_api import async_playwright

html = """
<table>
  <tr><td>( Year : 2025-26 Sem : 6 Degree... )</td></tr>
  <tr><td>Time Table (CORE)</td></tr>
  <tr>
    <td></td>
    <td>T1<br>08:00-09:00</td>
    <td>T2<br>09:00-10:00</td>
  </tr>
  <tr>
    <td>Mon</td>
    <td>Eng</td>
    <td>Math</td>
  </tr>
  <tr>
    <td>Tue</td>
    <td>Eng</td>
    <td>Math</td>
  </tr>
  <tr>
    <td>Sat</td>
    <td></td>
    <td></td>
  </tr>
  <tr><td>Legend - Something / Guy</td></tr>

  <tr><td>( Year : ... )</td></tr>
  <tr><td>Time Table (ELECTIVES)</td></tr>
  <tr>
    <td></td>
    <td>T1<br>08:00-09:00</td>
    <td>T2<br>09:00-10:00</td>
  </tr>
  <tr>
    <td>Mon</td>
    <td>Elec1</td>
    <td>Elec2</td>
  </tr>
</table>
"""

js_code = """
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
            // Need to match headers like T1, T2
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
                if (h > 0 && back <= headerRowIndices[h-1]) break;
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
"""

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html)
        res = await page.evaluate(js_code)
        import json
        print(json.dumps(res, indent=2))
        await browser.close()

asyncio.run(run())
