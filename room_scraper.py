"""
IMS NSIT Room Timetable Scraper
Scrapes availability data for ALL rooms by iterating through room numbers
"""

import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime
import os
from dotenv import load_dotenv
import re

load_dotenv()


class RoomTimetableScraper:
    def __init__(self, user_id: str = None, password: str = None, fin_year: str = "2025-26"):
        self.user_id = user_id or os.getenv('IMS_USER_ID')
        self.password = password or os.getenv('IMS_PASSWORD')
        self.fin_year = fin_year
        self.base_url = "https://www.imsnsit.org/imsnsit/"
        
        # Define room ranges to scrape
        self.room_ranges = self.generate_room_ranges()
        
    def generate_room_ranges(self):
        """
        Targets the entire fifth block: 5000-5040, 5100-5140, 5200-5240, 5300-5320
        """
        return [
            range(5000, 5030),
            range(5100, 5130),
            range(5200, 5231),
            range(5300, 5321)
        ]
        
    async def bypass_all_protections(self, page):
        """Bypass debugger and anti-scraping measures"""
        await page.evaluate("""
            // Override debugger
            window.debugger = () => {};
            
            // Block anti-debug intervals
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
            
            // Clear existing intervals
            for (let i = 0; i < 10000; i++) {
                try { clearInterval(i); } catch(e) {}
            }
            
            // Override setTimeout for debugger
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
        # Try finding by value, fallback to text
        try:
            login_btn_selector = 'input[value="Student Login"]'
            await page.wait_for_selector(login_btn_selector, state='visible', timeout=10000)
            await page.click(login_btn_selector)
        except:
            print("⚠️ Initial click failed. Trying alternative selector...")
            await page.click('text="Student Login"')
            
        await page.wait_for_load_state('domcontentloaded')
        await self.bypass_all_protections(page)
        
        print(f"📝 Entering credentials for {self.user_id}...")
        
        # Wait for frame
        print("🖼️  Waiting for login frame...")
        try:
            # Wait for the frame to be attached
            element_handle = await page.wait_for_selector('frame[name="banner"]', timeout=10000)
            frame = await element_handle.content_frame()
            if not frame:
                print("⚠️  Frame 'banner' found but content_frame is None. Trying to find by name directly.")
                frame = page.frame(name="banner")
        except:
            print("⚠️  Could not find frame by selector, trying by name lookup...")
            frame = page.frame(name="banner")
            
        if not frame:
            print("❌ Login frame 'banner' not found! Trying main page as fallback...")
            frame = page
            
        # Fill inputs
        try:
            await frame.fill('input[name="txtuserid"]', self.user_id, timeout=5000)
        except:
            print("⚠️  'txtuserid' not found, trying placeholder...")
            await frame.fill('input[placeholder="Enter userid"]', self.user_id)
            
        try:
            await frame.fill('input[name="txtpassword"]', self.password, timeout=5000)
        except:
            print("⚠️  'txtpassword' not found, trying placeholder...")
            await frame.fill('input[placeholder="Enter password"]', self.password)

        try:
            await frame.select_option('select[name="cmbfinyear"]', self.fin_year, timeout=3000)
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
            await frame.click('input[value="Login"]', timeout=5000)
        except:
            print("⚠️ Login button not found by value, trying type...")
            await frame.click('input[type="submit"]', timeout=5000)
            
        await page.wait_for_load_state('networkidle', timeout=30000)
        await self.bypass_all_protections(page)
        
        try:
            # Check in main page and frames for Welcome message
            success = False
            try:
                if await page.query_selector('text=/Welcome/i'):
                    success = True
            except: pass
            
            if not success:
                for f in page.frames:
                    try:
                        if await f.query_selector('text=/Welcome/i'):
                            success = True
                            break
                    except: pass
        except:
            pass
        
        if success:
            print("✅ Login successful!")
            
            # Dump dashboard content
            try:
                content = await page.content()
                os.makedirs(os.path.expanduser("~/ims_scraper_outputs"), exist_ok=True)
                with open(os.path.expanduser("~/ims_scraper_outputs/dashboard.html"), "w") as f:
                    f.write(content)
                print("📄 Saved dashboard content to ~/ims_scraper_outputs/dashboard.html")
            except Exception as e:
                print(f"⚠️ Could not dump dashboard content: {e}")
            
            return True
        else:
            print("❌ Login check failed")
            return False
    
    async def get_room_list(self, page):
        """
        Discover available rooms from the 'Pick Room' popup
        """
        print("\n🔍 Discovering available rooms...")
        rooms = []
        
        try:
            # 1. Find the "Pick Room" button/link in the main page (likely in a frame)
            pick_room_btn = None
            target_frame = None
            
            for frame in [page] + page.frames:
                try:
                    # Found in frame_5_data.html: <img src="images/enlarge.gif" border="0" title="Picker"> inside <a>
                    pick_room_btn = await frame.query_selector('img[title="Picker"]')
                    
                    if pick_room_btn:
                        # Get parent anchor
                        parent = await pick_room_btn.query_selector('xpath=..')
                        if parent:
                            pick_room_btn = parent
                        
                        target_frame = frame
                        print(f"   ✓ Found 'Pick Room' button in frame: {getattr(frame, 'name', 'main')}")
                        break
                except: continue
            
            if not pick_room_btn:
                print("⚠️  Could not find 'Pick Room' button (img[title='Picker']).")
                # Fallback to defaults
                return []
                
            # 2. Extract the popup URL from href="javascript:openURL('url', ...)"
            href = await pick_room_btn.get_attribute('href')
            popup_url = None
            
            if href:
                # Extract URL from openURL("...", ...)
                # It might use single or double quotes
                match = re.search(r"openURL\(['\"]([^'\"]+)['\"]", href)
                if match:
                    popup_url = match.group(1)
            
            if not popup_url:
                print(f"⚠️  Could not extract popup URL from href: {href}")
                return []
                
            # Construct absolute URL
            if not popup_url.startswith('http'):
                base_url = target_frame.url
                from urllib.parse import urljoin
                popup_url = urljoin(base_url, popup_url)
                
            print(f"   🔗 Popup URL: {popup_url}")
            
            # 3. Trigger popup by clicking and wait for it
            print("   ⏳ Triggering room list popup...")
            try:
                # Capture the popup
                async with page.context.expect_event("popup") as popup_info:
                    await pick_room_btn.click()
                
                popup_page = await popup_info.value
                await popup_page.wait_for_load_state('networkidle')
                
                # Debug: Dump popup content
                try:
                    p_content = await popup_page.content()
                    with open(os.path.expanduser("~/ims_scraper_outputs/room_list_popup.html"), "w") as f:
                        f.write(p_content)
                    print(f"📄 Saved popup content to ~/ims_scraper_outputs/room_list_popup.html")
                except: pass

                # 4. Scrape the list
                # The popup might have its own frames
                for p_frame in [popup_page] + popup_page.frames:
                    links = await p_frame.query_selector_all('a')
                    if links:
                        print(f"   Found {len(links)} links in popup frame: {getattr(p_frame, 'name', 'main')}")
                        
                        for link in links:
                            text = await link.inner_text()
                            text = text.strip()
                            href = await link.get_attribute('href')
                            
                            # Usually: javascript:SetVal('108','G-108')
                            val = text
                            if href and 'javascript' in href:
                                # Extract FIRST argument as the code (value) and SECOND as the text
                                # javascript:Pick('CODE','TEXT') or similar
                                match = re.search(r"['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", href)
                                if match:
                                    val = match.group(1)
                                    text = match.group(2)
                                else:
                                    # Try single arg
                                    match = re.search(r"\(['\"]([^'\"]+)['\"]\)", href)
                                    if match:
                                        val = match.group(1)
                            
                            if text and len(text) < 40 and text not in ['Search', 'Close', 'Logout']:
                                 rooms.append({'value': val, 'text': text})

                await popup_page.close()
                
            except Exception as e:
                print(f"⚠️  Error handling popup: {e}")
                return []
                
            # De-duplicate
            unique_rooms = {v['text']:v for v in rooms}.values()
            rooms = list(unique_rooms)
            
            print(f"   ✓ Discovered {len(rooms)} rooms.")
            return rooms

        except Exception as e:
            print(f"⚠️  Error in room discovery: {e}")
            return []

    async def navigate_to_room_timetable(self, page):
        """Navigate to RoomTimetable page manually"""
        print("\n" + "="*60)
        print("📍 MANUAL NAVIGATION REQUIRED")
        print("1. Go to the browser window")
        print("2. Navigate to 'TIME TABLE' -> 'RoomTimetable'")
        print("3. Ensure you can see the Room List / Dropdown")
        print("   (Click 'List of Rooms' button if needed)")
        print("\n   Press ENTER in this terminal when ready...")
        print("="*60 + "\n")
        
        await asyncio.get_event_loop().run_in_executor(None, input)
        print("✅ Proceeding with room discovery...")
        
        # Determine if we need to switch frame context
        # We'll just wait a bit and handle protection
        await page.wait_for_timeout(2000)
        await self.bypass_all_protections(page)
        
        # Debug: Dump content to check frames and selectors
        try:
            print(f"   Frames found: {[f.name for f in page.frames]}")
            content = await page.content()
            with open(os.path.expanduser("~/ims_scraper_outputs/room_discovery_page.html"), "w") as f:
                f.write(content)
            print("📄 Saved discovery page content to ~/ims_scraper_outputs/room_discovery_page.html")
            
            # Also dump frame contents
            for i, f in enumerate(page.frames):
                try:
                    c = await f.content()
                    with open(os.path.expanduser(f"~/ims_scraper_outputs/frame_{i}_{f.name or 'unnamed'}.html"), "w") as file:
                        file.write(c)
                except: pass
        except: pass
        
        return True

    async def scrape_room_timetable(self, page, room_identifier, semester: str = "ODD"):
        """
        Scrape timetable for a specific room
        room_identifier: can be a simple string (room number) or a dict {value, text} from dropdown
        """
        room_value = room_identifier if isinstance(room_identifier, str) else room_identifier['value']
        room_text = room_identifier if isinstance(room_identifier, str) else room_identifier.get('text', str(room_value))
        
        try:
            # Determine how to input the room (Input field vs Dropdown)
            target_frame = page
            
            # Select semester (if present)
            try:
                # Try in all frames
                for frame in [page] + page.frames:
                    try:
                        await frame.select_option('select[name="semcmb"]', semester, timeout=1000)
                        target_frame = frame
                        break
                    except: pass
            except: pass
            
            # Input Room
            input_found = False
            for frame in [page] + page.frames:
                # Try to find the visible input
                visible_input = await frame.query_selector('input[name="room"]') or \
                                await frame.query_selector('input[id="txtroom"]')
                                
                if visible_input:
                    target_frame = frame
                    print(f"   ✓ Found visible room input in frame: {getattr(frame, 'name', 'main')}")
                    
                    # We need to set BOTH visible and hidden inputs
                    room_val = room_identifier['value'] if isinstance(room_identifier, dict) else str(room_identifier)
                    room_text = room_identifier['text'] if isinstance(room_identifier, dict) else str(room_identifier)
                    
                    print(f"   ✍️  Setting room to: {room_text}")
                    
                    # Use JS to set values and CLEAR PREVIOUS RESULTS
                    await frame.evaluate(f"""
                        () => {{
                            // Clear previous table if any to ensure we wait for NEW data
                            const tables = document.querySelectorAll('table');
                            tables.forEach(t => {{
                                if (t.innerText.includes('TIME TABLE')) t.innerHTML = '<tr><td>Loading...</td></tr>';
                            }});
                            
                            // Set visible text
                            const visible = document.getElementById('txtroom') || document.querySelector('input[name="room"]');
                            if (visible) {{
                                visible.value = '{room_text}';
                                visible.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                visible.dispatchEvent(new Event('change', {{ bubbles: true }}));
                            }}
                            
                            // Set hidden code
                            const hidden = document.getElementById('txtroomcode') || document.querySelector('input[name="roomcode"]');
                            if (hidden) {{
                                hidden.value = '{room_val}';
                            }}
                        }}
                    """)
                    
                    input_found = True
                    break
            
            if not input_found:
                 print(f"⚠️  Could not find room input fields (txtroom/txtroomcode)")
                 return None

            # Click Go button
            try:
                go_btn = await target_frame.query_selector('input[value="Go"]') or \
                         await target_frame.query_selector('input[type="submit"]')
                
                if go_btn:
                    print("   🖱️  Clicking Go...")
                    await go_btn.click()
                else:
                    print("⚠️  Could not find Go button")
                    return None
            except Exception as e:
                print(f"⚠️  Error clicking Go: {e}")
                return None
            
            # --- Robust Wait for Data ---
            # Increase wait time and poll for content
            print("   ⏳ Waiting for data to load...", end=" ")
            data_found = False
            start_time = datetime.now()
            
            for i in range(15): # Max 15 seconds
                await asyncio.sleep(1)
                
                # Check for table or "No data found"
                if hasattr(target_frame, 'text_content'):
                    text = await target_frame.text_content('body')
                else:
                    text = await target_frame.evaluate('document.body.innerText')
                
                # Look for a table with rows (excluding header-only and our "Loading..." placeholder)
                table_check = await target_frame.evaluate("""
                    () => {
                        const tables = document.querySelectorAll('table');
                        for (const table of tables) {
                            // The timetable typically has cells with class 'plum_fieldbig'
                            const hasPlumField = table.querySelector('.plum_fieldbig');
                            const rows = table.querySelectorAll('tr');
                            if (hasPlumField && rows.length > 2) {
                                return true;
                            }
                        }
                        return false;
                    }
                """)
                
                if table_check:
                    data_found = True
                    print(f"✓ Loaded ({i+1}s)")
                    # Give it one extra second to be absolutely sure JS rendering is done
                    await asyncio.sleep(1)
                    break
                
                # Double check for "No data found" ONLY after a few seconds to avoid catching old state
                if i > 5 and ('No data found' in text or 'not available' in text.lower()):
                    print("✗ No data")
                    return None
            
            if not data_found:
                print("⚠️  Timeout waiting for data")
                # Dump content for debugging if it times out
                try:
                    debug_content = await target_frame.content()
                    with open(os.path.expanduser(f"~/ims_scraper_outputs/timeout_{room_text}.html"), "w") as f:
                        f.write(debug_content)
                except: pass
                return None
            
            await self.bypass_all_protections(page)
            
            # Extract timetable data
            timetable_data = await target_frame.evaluate(f"""
                () => {{
                    const data = {{
                        room: "{room_text}",
                        semester: "{semester}",
                        year: null,
                        schedule: {{}}
                    }};
                    
                    // Find the timetable table using the plum_fieldbig class
                    let table = null;
                    const tables = document.querySelectorAll('table');
                    for (const t of tables) {{
                        if (t.querySelector('.plum_fieldbig')) {{
                            table = t;
                            break;
                        }}
                    }}
                    
                    if (!table) return null;
                    
                    // Extract room info from title if available
                    const title = document.querySelector('body')?.textContent || '';
                    const yearMatch = title.match(/Year\\s*:\\s*([\\d-]+)/i);
                    if (yearMatch) data.year = yearMatch[1];
                    
                    const rows = Array.from(table.querySelectorAll('tr'));
                    
                    // Header row (contains T1, T2...)
                    // Based on screenshot, headers are in a row with purple-ish background
                    const headerRow = rows.find(r => r.innerText.includes('T1') || r.innerText.includes('T2'));
                    if (!headerRow) return null;
                    
                    const timeSlots = [];
                    headerRow.querySelectorAll('td, th').forEach((cell, idx) => {{
                        if (idx > 0) {{ // Skip first column (day names)
                            timeSlots.push(cell.textContent.trim());
                        }}
                    }});
                    
                    // Body rows
                    const bodyRows = rows.filter(r => 
                        r.innerText.includes('Mon') || 
                        r.innerText.includes('Tue') || 
                        r.innerText.includes('Wed') || 
                        r.innerText.includes('Thu') || 
                        r.innerText.includes('Fri') || 
                        r.innerText.includes('Sat')
                    );
                    
                    for (const row of bodyRows) {{
                        const cells = Array.from(row.querySelectorAll('td, th'));
                        if (cells.length === 0) continue;
                        
                        const day = cells[0].textContent.trim();
                        data.schedule[day] = [];
                        
                        // Remaining cells are time slots
                        for (let j = 1; j < cells.length && (j-1) < timeSlots.length; j++) {{
                            const cell = cells[j];
                            const text = cell.textContent.trim().replace(/\\s+/g, ' ');
                            
                            data.schedule[day].push({{
                                time_slot: timeSlots[j-1],
                                content: text,
                                is_occupied: text.length > 5 // Heuristic: valid class info is longer than empty space
                            }});
                        }}
                    }}
                    
                    return data;
                }}
            """)
            
            if timetable_data and timetable_data.get('schedule'):
                return timetable_data
            else:
                return None
                
        except Exception as e:
            print(f"⚠️  Error scraping room {room_text}: {e}")
            return None

    async def scrape_all_rooms(self, page, semester: str = "ODD"):
        """
        Iterate through all discovered rooms
        """
        print("\n" + "="*60)
        print("📊 STARTING DYNAMIC ROOM SCRAPING")
        print("="*60 + "\n")
        
        # 1. Discover rooms first
        discovered_rooms = await self.get_room_list(page)
        
        if not discovered_rooms:
            print("⚠️  No rooms discovered dynamically. Falling back to configured ranges.")
            rooms_to_scrape = []
            for r in self.room_ranges:
                rooms_to_scrape.extend([str(x) for x in r])
        else:
            print(f"✅ Found {len(discovered_rooms)} rooms dynamically.")
            # Filter rooms by our target ranges
            rooms_to_scrape = []
            target_range_set = set()
            for r in self.room_ranges:
                target_range_set.update(str(x) for x in r)
            
            for room in discovered_rooms:
                room_txt = room['text'] if isinstance(room, dict) else str(room)
                # Try to extract the number if it's like "G-108" or "5301"
                match = re.search(r'(\d+)', room_txt)
                if match:
                    room_num_str = match.group(1)
                    if room_num_str in target_range_set:
                        rooms_to_scrape.append(room)
            
            print(f"🎯 Filtered to {len(rooms_to_scrape)} rooms in target ranges.")

        all_rooms_data = []
        total_rooms = len(rooms_to_scrape)
        
        for idx, room in enumerate(rooms_to_scrape, 1):
            room_label = room['text'] if isinstance(room, dict) else room
            print(f"   [{idx}/{total_rooms}] Room {room_label}...", end=" ")
            
            room_data = await self.scrape_room_timetable(page, room, semester)
            
            if room_data:
                all_rooms_data.append(room_data)
                print(f"✓ Found data")
            else:
                print(f"✗ No data")
            
            # Small delay to avoid overwhelming the server
            await page.wait_for_timeout(200)
        
        print("\n" + "="*60)
        print(f"✅ Scraping complete!")
        print(f"   Total rooms checked: {total_rooms}")
        print(f"   Rooms with data: {len(all_rooms_data)}")
        print("="*60 + "\n")
        
        return all_rooms_data

    async def scrape_specific_rooms(self, page, room_numbers: list, semester: str = "ODD"):
        # ... logic is similar, just using the passed list directly ...
        # For simplicity, we assume room_numbers provided here are simple strings/ints
        # which scrape_room_timetable handles.
        
        # Re-implementing simplified loop to match updated scrape_room_timetable signature
        print(f"\n📊 Scraping {len(room_numbers)} specific rooms...")
        all_rooms_data = []
        for idx, room_num in enumerate(room_numbers, 1):
            print(f"   [{idx}/{len(room_numbers)}] Room {room_num}...", end=" ")
            room_data = await self.scrape_room_timetable(page, str(room_num), semester)
            if room_data:
                all_rooms_data.append(room_data)
                print(f"✓")
            else:
                print(f"✗")
            await page.wait_for_timeout(200)
        return all_rooms_data
    
    async def analyze_availability(self, rooms_data):
        """
        Analyze room availability and generate insights
        """
        print("\n📈 Analyzing room availability...")
        
        analysis = {
            'total_rooms': len(rooms_data),
            'by_day': {},
            'by_time_slot': {},
            'most_available_rooms': [],
            'least_available_rooms': []
        }
        
        for room in rooms_data:
            room_number = room.get('room')
            schedule = room.get('schedule', {})
            
            total_slots = 0
            occupied_slots = 0
            
            for day, slots in schedule.items():
                if day not in analysis['by_day']:
                    analysis['by_day'][day] = {'total': 0, 'occupied': 0}
                
                for slot in slots:
                    total_slots += 1
                    analysis['by_day'][day]['total'] += 1
                    
                    time = slot.get('time_slot')
                    if time not in analysis['by_time_slot']:
                        analysis['by_time_slot'][time] = {'total': 0, 'occupied': 0}
                    
                    analysis['by_time_slot'][time]['total'] += 1
                    
                    if slot.get('is_occupied'):
                        occupied_slots += 1
                        analysis['by_day'][day]['occupied'] += 1
                        analysis['by_time_slot'][time]['occupied'] += 1
            
            if total_slots > 0:
                availability_pct = ((total_slots - occupied_slots) / total_slots) * 100
                room_info = {
                    'room': room_number,
                    'availability_percentage': round(availability_pct, 2),
                    'free_slots': total_slots - occupied_slots,
                    'total_slots': total_slots
                }
                
                if availability_pct >= 50:
                    analysis['most_available_rooms'].append(room_info)
                else:
                    analysis['least_available_rooms'].append(room_info)
        
        # Sort by availability
        analysis['most_available_rooms'].sort(
            key=lambda x: x['availability_percentage'], reverse=True
        )
        analysis['least_available_rooms'].sort(
            key=lambda x: x['availability_percentage']
        )
        
        return analysis
    
    async def save_data(self, rooms_data, analysis, filename='rooms_complete_data.json'):
        """Save all scraped data and analysis"""
        output = {
            'timestamp': datetime.now().isoformat(),
            'user_id': self.user_id,
            'fin_year': self.fin_year,
            'total_rooms': len(rooms_data),
            'analysis': analysis,
            'rooms': rooms_data
        }
        
        # Use user's home directory
        home_dir = os.path.expanduser("~")
        output_path = os.path.join(home_dir, "ims_scraper_outputs", filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Data saved to {output_path}")
        return output_path
    
    async def run(self, mode='all', room_list=None, headless=False, semester="ODD"):
        """
        Main execution
        mode: 'all' to scrape all rooms, 'specific' to scrape room_list
        """
        print("\n" + "="*60)
        print("🚀 IMS ROOM TIMETABLE SCRAPER")
        print("="*60 + "\n")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            self.browser = browser
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page = await context.new_page()
            
            try:
                # Login
                success = await self.login(page)
                if not success:
                    return
                
                # Navigate to room timetable
                await self.navigate_to_room_timetable(page)
                
                # Scrape based on mode
                if mode == 'specific' and room_list:
                    rooms_data = await self.scrape_specific_rooms(page, room_list, semester)
                else:
                    rooms_data = await self.scrape_all_rooms(page, semester)
                
                # Analyze data
                analysis = await self.analyze_availability(rooms_data)
                
                # Save everything
                await self.save_data(rooms_data, analysis)
                
                # Print summary
                print("\n" + "="*60)
                print("📊 SUMMARY")
                print("="*60)
                print(f"Total rooms found: {len(rooms_data)}")
                print(f"\nMost available rooms:")
                for room in analysis['most_available_rooms'][:5]:
                    print(f"  Room {room['room']}: {room['availability_percentage']}% available")
                print(f"\nLeast available rooms:")
                for room in analysis['least_available_rooms'][:5]:
                    print(f"  Room {room['room']}: {room['availability_percentage']}% available")
                print("="*60 + "\n")
                
                if not headless:
                    print("🔍 Browser kept open. Close to exit.")
                    await page.pause()
                
            except Exception as e:
                print(f"\n❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
            finally:
                if headless:
                    await browser.close()


async def main():
    """Example usage"""
    scraper = RoomTimetableScraper(
        user_id="2022UIT3042",
        password="vogsue-7",
        fin_year="2025-26"
    )
    
    # Option 1: Scrape ALL rooms (might take a while)
    await scraper.run(mode='all', headless=False, semester="ODD")
    
    # Option 2: Scrape specific rooms only
    # specific_rooms = [5306, 5307, 5308, 5309, 5310]
    # await scraper.run(mode='specific', room_list=specific_rooms, headless=False, semester="ODD")


if __name__ == "__main__":
    asyncio.run(main())
