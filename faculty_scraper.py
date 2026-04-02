"""
IMS NSIT Faculty Timetable Scraper
Scrapes availability data for faculties by iterating through names from Excel
"""

import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import re
import pandas as pd

load_dotenv()


class FacultyTimetableScraper:
    def __init__(self, user_id: str = None, password: str = None, fin_year: str = "2025-26"):
        self.user_id = user_id or os.getenv('IMS_USER_ID')
        self.password = password or os.getenv('IMS_PASSWORD')
        self.fin_year = fin_year
        self.base_url = "https://www.imsnsit.org/imsnsit/"
        
        # Load faculty list from Excel
        self.excel_path = "/Users/vasugoel/Downloads/Faculty Details.xlsx"
        self.faculty_names = self.load_faculties_from_excel(self.excel_path)
        
    def load_faculties_from_excel(self, file_path):
        """Load faculty names from the provided Excel file"""
        print(f"📊 Loading faculty details from {file_path}...")
        try:
            # Try to read Excel file
            df = pd.read_excel(file_path)
            
            # Look for a column that might contain faculty names
            possible_cols = ['Faculty Name', 'FacultyName', 'Name', 'Faculty', 'FACULTY NAME']
            name_col = None
            for col in df.columns:
                if any(p in col.upper() for p in [p.upper() for p in possible_cols]):
                    name_col = col
                    break
            
            if not name_col:
                # Fallback to the first column if no match found
                name_col = df.columns[0]
                print(f"⚠️  Could not find specific 'Faculty Name' column. Using first column: '{name_col}'")
            else:
                print(f"✅  Found faculty names in column: '{name_col}'")
                
            names = df[name_col].dropna().astype(str).str.strip().unique().tolist()
            print(f"📝  Loaded {len(names)} faculty names.")
            return names
        except Exception as e:
            print(f"❌  Error loading Excel file: {e}")
            print("💡  Ensure 'pandas' and 'openpyxl' are installed: pip install pandas openpyxl")
            return []

    async def bypass_all_protections(self, page):
        """Bypass debugger and anti-scraping measures"""
        await page.evaluate("""
            window.debugger = () => {};
            const originalSetInterval = window.setInterval;
            window.setInterval = function(callback, delay, ...args) {
                if (callback && typeof callback === 'function') {
                    const cbStr = callback.toString();
                    if (cbStr.match(/debugger|dbg|OffFF|d\\s*=\\s*new\\s+Date/i)) {
                        return -1;
                    }
                }
                return originalSetInterval(callback, delay, ...args);
            };
            for (let i = 0; i < 10000; i++) {
                try { clearInterval(i); } catch(e) {}
            }
            const originalSetTimeout = window.setTimeout;
            window.setTimeout = function(callback, delay, ...args) {
                if (callback && typeof callback === 'function') {
                    const cbStr = callback.toString();
                    if (cbStr.match(/debugger|dbg/i)) {
                        return -1;
                    }
                }
                return originalSetTimeout(callback, delay, ...args);
            };
        """)
    
    async def login(self, page):
        """Login to IMS portal"""
        print("🌐 Loading IMS portal...")
        await page.goto(self.base_url, wait_until='domcontentloaded')
        await self.bypass_all_protections(page)
        await page.wait_for_timeout(1000)
        
        print("🎓 Clicking Student Login...")
        try:
            login_btn_selector = 'input[value="Student Login"]'
            await page.wait_for_selector(login_btn_selector, state='visible', timeout=3000)
            await page.click(login_btn_selector)
        except:
            print("⚠️ Initial click failed. Trying alternative selector...")
            await page.click('text="Student Login"')
            
        await page.wait_for_load_state('domcontentloaded')
        await self.bypass_all_protections(page)
        
        print(f"📝 Entering credentials for {self.user_id}...")
        
        if not self.user_id or not self.password:
            print("\n" + "!"*60)
            print("❌ ERROR: IMS_USER_ID or IMS_PASSWORD not found!")
            print("Please ensure they are set in your .env file or environment variables.")
            print("!"*60 + "\n")
            return False

        print("🖼️  Waiting for login frame...")
        try:
            element_handle = await page.wait_for_selector('frame[name="banner"]', timeout=3000)
            frame = await element_handle.content_frame()
            if not frame:
                frame = page.frame(name="banner")
        except:
            frame = page.frame(name="banner")
            
        if not frame:
            print("❌ Login frame 'banner' not found! Trying main page as fallback...")
            frame = page
            
        try:
            await frame.wait_for_selector('input[name="txtuserid"]', timeout=3000)
            await frame.fill('input[name="txtuserid"]', str(self.user_id))
        except:
            await frame.fill('input[placeholder="Enter userid"]', str(self.user_id))
            
        try:
            await frame.fill('input[name="txtpassword"]', str(self.password), timeout=3000)
        except:
            await frame.fill('input[placeholder="Enter password"]', str(self.password))

        try:
            await frame.select_option('select[name="cmbfinyear"]', str(self.fin_year), timeout=3000)
        except:
            pass
        
        # Handle captcha
        print("\n" + "="*60)
        print("⏳ Please solve the captcha in the browser window")
        print("   Then press ENTER in this terminal...")
        print("="*60 + "\n")
        await asyncio.get_event_loop().run_in_executor(None, input)
        
        print("🔐 Logging in...")
        try:
            await frame.click('input[value="Login"]', timeout=3000)
        except:
            await frame.click('input[type="submit"]', timeout=3000)
            
        await page.wait_for_load_state('networkidle', timeout=30000)
        await self.bypass_all_protections(page)
        
        success = False
        try:
            if await page.query_selector('text=/Welcome/i'):
                success = True
            if not success:
                for f in page.frames:
                    if await f.query_selector('text=/Welcome/i'):
                        success = True
                        break
        except:
            pass
        
        if success:
            print("✅ Login successful!")
            return True
        else:
            print("❌ Login check failed")
            return False
    
    # get_faculty_list removed in favor of direct popup search

    async def navigate_to_faculty_timetable(self, page):
        """Navigate to Faculty Timetable page manually"""
        print("\n" + "="*60)
        print("📍 MANUAL NAVIGATION REQUIRED")
        print("1. Go to the browser window")
        print("2. Navigate to 'TIME TABLE' -> 'Faculty Timetable'")
        print("3. Ensure you can see the 'Pick Faculty' link")
        print("\n   Press ENTER in this terminal when ready...")
        print("="*60 + "\n")
        
        await asyncio.get_event_loop().run_in_executor(None, input)
        print("✅ Proceeding...")
        await page.wait_for_timeout(1000)
        await self.bypass_all_protections(page)
        return True

    async def scrape_faculty_timetable(self, page, faculty_name: str, semester: str = "EVEN"):
        """
        Scrape timetable for a specific faculty by searching in the popup
        """
        fac_text = faculty_name.upper().strip()
        
        try:
            target_frame = page
            
            # Select semester
            for frame in [page] + page.frames:
                try:
                    await frame.select_option('select[name="sem"]', semester, timeout=1000)
                    target_frame = frame
                    break
                except: pass
            
            # Find the pick faculty button and trigger popup
            pick_faculty_btn = None
            for frame in [page] + page.frames:
                try:
                    pick_faculty_btn = await frame.query_selector('img[title="Picker"]') or \
                                      await frame.query_selector('text="Pick Faculty"') or \
                                      await frame.query_selector('a:has-text("Pick")')
                    if pick_faculty_btn:
                        if await pick_faculty_btn.evaluate('el => el.tagName === "IMG"'):
                            parent = await pick_faculty_btn.query_selector('xpath=..')
                            if parent: pick_faculty_btn = parent
                        
                        target_frame = frame
                        break
                except: continue
                
            if not pick_faculty_btn:
                print(f"⚠️  Could not find 'Pick Faculty' button for {fac_text}")
                return None
                
            # Trigger popup
            popup_page = None
            try:
                # Wait for any previous popups to close if necessary
                async with page.context.expect_event("popup", timeout=10000) as popup_info:
                    await pick_faculty_btn.click()
                popup_page = await popup_info.value
            except Exception as e:
                if len(page.context.pages) > 1:
                    popup_page = page.context.pages[-1]
                else:
                    print(f"      ⚠️  Popup failed to open: {e}")
                    return None
            
            await popup_page.wait_for_load_state('networkidle')
            await popup_page.wait_for_timeout(1000)
            
            # Input search string into popup
            try:
                # Try finding frame inside popup if any
                f_target = popup_page
                for pf in popup_page.frames:
                    if await pf.query_selector('input[name="search"]'):
                        f_target = pf
                        break
                        
                await f_target.fill('input[name="search"]', fac_text)
                await f_target.click('input[name="proceed"], input[value="Search"]')
                
                # Wait for search results
                await f_target.wait_for_timeout(1500)
                
                # Click the first a-tag result (skipping Search, Close, Logout)
                links = await f_target.query_selector_all('a')
                clicked = False
                for link in links:
                    txt = (await link.inner_text()).strip().upper()
                    if txt and txt not in ['SEARCH', 'CLOSE', 'LOGOUT'] and 'EXT' not in txt and 'T2' not in txt:
                        clean_txt = txt.split(';')[0].strip()
                        if fac_text in clean_txt or clean_txt in fac_text:
                            await link.click()
                            clicked = True
                            break
                            
                # Fallback purely to first available
                if not clicked and links:
                    for link in links:
                        txt = (await link.inner_text()).strip()
                        if txt and txt not in ['Search', 'Close', 'Logout']:
                            await link.click()
                            clicked = True
                            break
                            
                if not clicked:
                    print(f"      ⚠️  No matching records found for {fac_text} in popup")
                    await popup_page.close()
                    return None
                    
                # Wait for popup to close and main page to receive values
                for _ in range(10):
                    if popup_page.is_closed():
                        break
                    await asyncio.sleep(0.5)
                    
                if not popup_page.is_closed():
                    await popup_page.close()
                    
            except Exception as e:
                print(f"      ⚠️  Error processing popup: {e}")
                if not popup_page.is_closed():
                    await popup_page.close()
                return None

            # Click Proceed button on main page
            try:
                proceed_btn = await target_frame.query_selector('input[value="Proceed"]') or \
                              await target_frame.query_selector('input[value="Go"]') or \
                              await target_frame.query_selector('input[type="submit"]')
                if proceed_btn:
                    await proceed_btn.click()
                else:
                    return None
            except:
                return None
            
            # Wait for Data
            data_found = False
            for i in range(10):
                await asyncio.sleep(1)
                
                table_check = await target_frame.evaluate("""
                    () => {
                        const tables = document.querySelectorAll('table');
                        for (const table of tables) {
                            const hasPlumField = table.querySelector('.plum_fieldbig');
                            const rows = table.querySelectorAll('tr');
                            if (hasPlumField && rows.length > 2) return true;
                            if (table.innerText.includes('T1') && table.innerText.includes('T2')) return true;
                        }
                        return false;
                    }
                """)
                
                if table_check:
                    data_found = True
                    await asyncio.sleep(5)
                    break
            
            if not data_found:
                return None
            
            await self.bypass_all_protections(page)
            
            # Extract timetable data
            timetable_data = await target_frame.evaluate(f"""
                () => {{
                    const data = {{
                        faculty: "{fac_text}",
                        semester: "{semester}",
                        schedule: {{}}
                    }};
                    
                    let table = null;
                    const tables = document.querySelectorAll('table');
                    for (const t of tables) {{
                        const txt = t.innerText;
                        if (txt.includes('T1') || txt.includes('T2') || t.querySelector('.plum_fieldbig')) {{
                            table = t;
                            break;
                        }}
                    }}
                    
                    if (!table) return null;
                    
                    const rows = Array.from(table.querySelectorAll('tr'));
                    const headerRow = rows.find(r => r.innerText.includes('T1') || r.innerText.includes('T2'));
                    if (!headerRow) return null;
                    
                    const timeSlots = [];
                    headerRow.querySelectorAll('td, th').forEach((cell, idx) => {{
                        if (idx > 0) timeSlots.push(cell.textContent.trim());
                    }});
                    
                    const bodyRows = rows.filter(r => 
                        /Mon|Tue|Wed|Thu|Fri|Sat/i.test(r.innerText)
                    );
                    
                    for (const row of bodyRows) {{
                        const cells = Array.from(row.querySelectorAll('td, th'));
                        if (cells.length === 0) continue;
                        
                        const day = cells[0].textContent.trim();
                        data.schedule[day] = [];
                        
                        for (let j = 1; j < cells.length && (j-1) < timeSlots.length; j++) {{
                            const cell = cells[j];
                            const text = cell.textContent.trim().replace(/\\s+/g, ' ');
                            data.schedule[day].push({{
                                time_slot: timeSlots[j-1],
                                content: text,
                                is_occupied: text.length > 5
                            }});
                        }}
                    }}
                    return data;
                }}
            """)
            
            return timetable_data
                
        except Exception as e:
            print(f"⚠️  Error scraping faculty {fac_text}: {e}")
            return None

    async def save_data(self, fac_data, filename='faculties_data.json'):
        """Save all scraped data"""
        output = {
            'timestamp': datetime.now().isoformat(),
            'user_id': self.user_id,
            'fin_year': self.fin_year,
            'faculties': fac_data
        }
        
        home_dir = os.path.expanduser("~")
        output_path = os.path.join(home_dir, "ims_scraper_outputs", "faculties", filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Data saved to {output_path}")
        return output_path
    
    async def run(self, headless=False, semester="EVEN"):
        """Main execution"""
        print("\n" + "="*60)
        print("🚀 IMS FACULTY TIMETABLE SCRAPER")
        print("="*60 + "\n")

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=['--disable-blink-features=AutomationControlled', '--no-sandbox']
            )
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
            page = await context.new_page()
            
            try:
                success = await self.login(page)
                if not success: return
                
                await self.navigate_to_faculty_timetable(page)
                
                if not self.faculty_names:
                    print("❌ No faculty names loaded from Excel. Exiting.")
                    return

                all_faculties_data = []
                print(f"\n🎯 Processing {len(self.faculty_names)} faculties from Excel (Search Workflow)...")
                
                for idx, fac_name in enumerate(self.faculty_names, 1):
                    name_parts = fac_name.strip().split(';')
                    fac_name_clean = name_parts[0].strip()
                    
                    print(f"   [{idx}/{len(self.faculty_names)}] Faculty: {fac_name_clean}...", end=" ")
                    
                    fac_data = await self.scrape_faculty_timetable(page, fac_name_clean, semester)
                    if fac_data:
                        all_faculties_data.append(fac_data)
                        print("✓")
                    else:
                        print("✗ (No timetable found)")
                        
                    await page.wait_for_timeout(300)
                        
                    await page.wait_for_timeout(300)
                
                # Save results
                if all_faculties_data:
                    await self.save_data(all_faculties_data)
                
                print("\n" + "="*60)
                print(f"✅ Scraping complete! Saved {len(all_faculties_data)} faculties.")
                print("="*60 + "\n")
                
            except Exception as e:
                print(f"❌ Fatal error: {e}")
            finally:
                if not headless:
                    print("🔍 Browser open for inspection. Press Ctrl+C to exit.")
                    await asyncio.get_event_loop().run_in_executor(None, input)
                await browser.close()


if __name__ == "__main__":
    scraper = FacultyTimetableScraper()
    asyncio.run(scraper.run(headless=False))
