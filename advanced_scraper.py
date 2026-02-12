"""
Advanced IMS NSIT Portal Scraper
With specific selectors and enhanced features
"""

import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

class AdvancedIMSScraper:
    def __init__(self, user_id: str = None, password: str = None, fin_year: str = "2025-26"):
        self.user_id = user_id or os.getenv('IMS_USER_ID')
        self.password = password or os.getenv('IMS_PASSWORD')
        self.fin_year = fin_year
        self.base_url = "https://www.imsnsit.org/imsnsit/"
        
    async def bypass_all_protections(self, page):
        """
        Comprehensive bypass for all anti-scraping measures
        """
        await page.evaluate("""
            // 1. Override debugger
            const noop = () => {};
            window.debugger = noop;
            
            // 2. Block anti-debug intervals
            const originalSetInterval = window.setInterval;
            window.setInterval = function(callback, delay, ...args) {
                const cbStr = callback.toString();
                // Block debugger-related intervals
                if (cbStr.match(/debugger|dbg|OffFF|d\s*=\s*new\s+Date/i)) {
                    console.log('🛡️ Blocked anti-scraping interval');
                    return -1;
                }
                return originalSetInterval(callback, delay, ...args);
            };
            
            // 3. Clear existing intervals
            for (let i = 0; i < 10000; i++) {
                try { clearInterval(i); } catch(e) {}
            }
            
            // 4. Override setTimeout for debugger
            const originalSetTimeout = window.setTimeout;
            window.setTimeout = function(callback, delay, ...args) {
                const cbStr = callback.toString();
                if (cbStr.match(/debugger|dbg/i)) {
                    console.log('🛡️ Blocked anti-scraping timeout');
                    return -1;
                }
                return originalSetTimeout(callback, delay, ...args);
            };
            
            // 5. Prevent DevTools detection
            const devtools = /./;
            devtools.toString = function() {
                return '';
            };
            
            console.log('✅ All protections bypassed');
        """)
    
    async def wait_and_bypass(self, page, timeout=2000):
        """
        Wait and reapply bypass (use after navigation)
        """
        await page.wait_for_timeout(timeout)
        await self.bypass_all_protections(page)
    
    async def solve_captcha_interactive(self, page):
        """
        Interactive captcha solving
        """
        print("\n" + "="*60)
        print("⏳ CAPTCHA DETECTED")
        print("="*60)
        print("Please solve the captcha in the browser window.")
        print("After solving, press ENTER in this terminal...")
        print("="*60 + "\n")
        
        # Wait for user input
        await asyncio.get_event_loop().run_in_executor(None, input)
        await asyncio.sleep(1)
    
    async def login(self, page):
        """
        Login to IMS portal
        """
        print("🌐 Loading IMS portal...")
        await page.goto(self.base_url, wait_until='domcontentloaded')
        await self.wait_and_bypass(page)
        
        # Click Student Login button
        print("🎓 Clicking Student Login...")
        try:
            # Wait for the button to be visible first
            login_btn_selector = 'input[value="Student Login"]'
            await page.wait_for_selector(login_btn_selector, state='visible', timeout=10000)
            await page.click(login_btn_selector)
        except Exception as e:
            print(f"⚠️ Initial click failed: {e}. Trying alternative selector/method...")
            # Try finding by text if value selector fails
            await page.click('text="Student Login"')
        await page.wait_for_load_state('domcontentloaded')
        await self.wait_and_bypass(page)
        
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
            print("❌ Login frame 'banner' not found! Dumping frames...")
            print(f"Frames: {page.frames}")
            raise Exception("Login frame not found")

        print("📝 Filling User ID in frame...")
        # Try multiple potential selectors for User ID
        try:
            await frame.fill('input[name="txtuserid"]', self.user_id, timeout=5000)
        except:
            print("⚠️  'txtuserid' not found, trying placeholder...")
            await frame.fill('input[placeholder="Enter userid"]', self.user_id)
            
        print("📝 Filling Password...")
        try:
            await frame.fill('input[name="txtpassword"]', self.password, timeout=5000)
        except:
            print("⚠️  'txtpassword' not found, trying placeholder...")
            await frame.fill('input[placeholder="Enter password"]', self.password)

        # Select financial year (might be static text or hidden)
        print("📅 Handling Financial Year...")
        try:
            await frame.select_option('select[name="cmbfinyear"]', self.fin_year, timeout=3000)
        except Exception as e:
            print(f"⚠️  Could not select Financial Year (might be static or different selector): {e}")

        # Handle captcha
        # Note: CAPTCHA might also be in the frame. We need to tell the user to check the frame.
        print("\n" + "="*60)
        print("⏳ CAPTCHA DETECTED")
        print("="*60)
        print("Please solve the captcha in the browser window.")
        print("After solving, press ENTER in this terminal...")
        print("="*60 + "\n")
        
        # Wait for user input
        await asyncio.get_event_loop().run_in_executor(None, input)
        await asyncio.sleep(1)
        
        # Click login
        print("🔐 Logging in...")
        try:
            await frame.click('input[value="Login"]', timeout=5000)
        except:
            print("⚠️ Login button by value not found, trying by type/text...")
            await frame.click('input[type="submit"]', timeout=5000)
        
        # Wait for login to complete - this might navigate the top page or just the frame
        await page.wait_for_load_state('networkidle', timeout=30000)
        await self.wait_and_bypass(page)
        
        # Verify login success
        try:
            # Check if we see "Welcome" text in the frame or page
            # Usually after login, the frameset might change or redirect
            await page.wait_for_timeout(2000) 
            
            # Check in main page and frames
            welcome_found = False
            try:
                if await page.query_selector('text=/Welcome/i'):
                    welcome_found = True
            except: pass
            
            if not welcome_found:
                for f in page.frames:
                    try:
                        if await f.query_selector('text=/Welcome/i'):
                            welcome_found = True
                            print(f"✅ Found welcome message in frame: {f.name}")
                            break
                    except: pass
            
            if welcome_found:
                print("✅ Login successful!")
                return True
            else:
                print("⚠️  Welcome message not found, but continuing (might be a false negative)...")
                return True
        except:
            print("❌ Login check failed.")
            return False
    
    async def get_all_links(self, page):
        """
        Extract all navigation links to help find room allocation
        """
        links = await page.evaluate("""
            () => {
                const links = [];
                document.querySelectorAll('a').forEach(a => {
                    links.push({
                        text: a.textContent.trim(),
                        href: a.href,
                        id: a.id,
                        class: a.className
                    });
                });
                return links;
            }
        """)
        return links
    
    async def navigate_to_room_allocation(self, page, manual=True):
        """
        Navigate to room allocation page
        """
        print("\n🏢 Navigating to room allocation...")
        
        if manual:
            print("\n" + "="*60)
            print("📍 MANUAL NAVIGATION REQUIRED")
            print("="*60)
            print("Please click on the room allocation link/menu item")
            print("in the browser window, then press ENTER here...")
            print("="*60 + "\n")
            
            await asyncio.get_event_loop().run_in_executor(None, input)
            await page.wait_for_load_state('networkidle')
            await self.wait_and_bypass(page)
            print("✅ Navigation complete!")
            return
        
        # Automatic navigation (you can update selectors based on your portal)
        try:
            # Try common link texts
            link_patterns = [
                'room allocation',
                'room',
                'allocation',
                'my activities'
            ]
            
            for pattern in link_patterns:
                try:
                    await page.click(f'text=/{pattern}/i', timeout=3000)
                    await page.wait_for_load_state('networkidle')
                    await self.wait_and_bypass(page)
                    print(f"✅ Found and clicked: {pattern}")
                    return
                except:
                    continue
            
            # If nothing works, fall back to manual
            print("⚠️  Automatic navigation failed, switching to manual...")
            await self.navigate_to_room_allocation(page, manual=True)
            
        except Exception as e:
            print(f"❌ Navigation error: {e}")
    
    async def scrape_table_data(self, page):
        """
        Extract data from all tables on the page
        """
        print("📊 Extracting table data...")
        
        tables_data = await page.evaluate("""
            () => {
                const allTables = [];
                const tables = document.querySelectorAll('table');
                
                tables.forEach((table, tableIndex) => {
                    const tableData = {
                        index: tableIndex,
                        headers: [],
                        rows: []
                    };
                    
                    // Extract headers
                    const headers = table.querySelectorAll('thead th, thead td, tr:first-child th');
                    if (headers.length > 0) {
                        tableData.headers = Array.from(headers).map(h => h.textContent.trim());
                    }
                    
                    // Extract rows
                    const rows = table.querySelectorAll('tbody tr, tr');
                    rows.forEach((row, rowIndex) => {
                        // Skip header row if no thead
                        if (rowIndex === 0 && tableData.headers.length === 0) {
                            const cells = row.querySelectorAll('th, td');
                            tableData.headers = Array.from(cells).map(c => c.textContent.trim());
                            return;
                        }
                        
                        const cells = row.querySelectorAll('td, th');
                        if (cells.length > 0) {
                            const rowData = Array.from(cells).map(cell => cell.textContent.trim());
                            tableData.rows.push(rowData);
                        }
                    });
                    
                    if (tableData.rows.length > 0) {
                        allTables.push(tableData);
                    }
                });
                
                return allTables;
            }
        """)
        
        return tables_data
    
    async def scrape_custom_data(self, page):
        """
        Extract data using custom selectors (update based on your needs)
        """
        print("🔍 Extracting custom data...")
        
        custom_data = await page.evaluate("""
            () => {
                const data = {
                    title: document.title,
                    url: window.location.href,
                    timestamp: new Date().toISOString(),
                    content: []
                };
                
                // Extract all divs with class containing 'room' or 'allocation'
                document.querySelectorAll('[class*="room"], [class*="allocation"]').forEach(el => {
                    data.content.push({
                        type: 'room_related',
                        class: el.className,
                        text: el.textContent.trim().substring(0, 200)
                    });
                });
                
                return data;
            }
        """)
        
        return custom_data
    
    async def take_screenshot(self, page, name='screenshot'):
        """
        Save screenshot for debugging
        """
        # Use user's home directory
        home_dir = os.path.expanduser("~")
        screenshot_dir = os.path.join(home_dir, "ims_scraper_screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)
        
        screenshot_path = os.path.join(screenshot_dir, f'{name}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png')
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"📸 Screenshot saved: {screenshot_path}")
        return screenshot_path
    
    async def save_data(self, data, filename='ims_room_data.json'):
        """
        Save data to JSON file
        """
        output = {
            'timestamp': datetime.now().isoformat(),
            'user_id': self.user_id,
            'fin_year': self.fin_year,
            'data': data
        }
        
        # Use user's home directory
        home_dir = os.path.expanduser("~")
        output_path = os.path.join(home_dir, "ims_scraper_outputs", filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Data saved to {output_path}")
        return output_path
    
    async def run(self, headless=False, auto_navigate=False):
        """
        Main scraping workflow
        """
        print("\n" + "="*60)
        print("🚀 IMS NSIT SCRAPER - STARTING")
        print("="*60 + "\n")
        
        async with async_playwright() as p:
            # Launch browser
            print("🌐 Launching browser...")
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-web-security'
                ]
            )
            
            # Create context
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True
            )
            
            # Hide automation
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                window.chrome = {
                    runtime: {}
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)
            
            page = await context.new_page()
            
            try:
                # Step 1: Login
                success = await self.login(page)
                if not success:
                    print("❌ Login failed. Exiting...")
                    return
                
                await self.take_screenshot(page, 'after_login')
                
                # Step 2: Navigate to room allocation
                await self.navigate_to_room_allocation(page, manual=not auto_navigate)
                
                await self.take_screenshot(page, 'room_allocation_page')
                
                # Step 3: Scrape data
                print("\n" + "="*60)
                print("📊 SCRAPING DATA")
                print("="*60 + "\n")
                
                table_data = await self.scrape_table_data(page)
                custom_data = await self.scrape_custom_data(page)
                
                # Combine all data
                all_data = {
                    'tables': table_data,
                    'custom': custom_data,
                    'page_url': page.url
                }
                
                # Step 4: Save data
                output_file = await self.save_data(all_data)
                
                print("\n" + "="*60)
                print("✅ SCRAPING COMPLETED SUCCESSFULLY!")
                print("="*60)
                print(f"📊 Tables found: {len(table_data)}")
                print(f"📁 Data saved to: {output_file}")
                print("="*60 + "\n")
                
                # Keep browser open for inspection if not headless
                if not headless:
                    print("🔍 Browser kept open for inspection.")
                    print("   Close the browser window to exit.\n")
                    await page.pause()
                
            except Exception as e:
                print(f"\n❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
                
                # Take error screenshot
                await self.take_screenshot(page, 'error')
                
            finally:
                if headless:
                    await browser.close()


# Main execution
async def main():
    """
    Example usage
    """
    scraper = AdvancedIMSScraper(
        user_id="2022UIT3042",  # Or use env variable
        password="vogsue-7",  # Or use env variable
        fin_year="2025-26"
    )
    
    # Run with visible browser and manual navigation
    await scraper.run(headless=False, auto_navigate=False)


if __name__ == "__main__":
    asyncio.run(main())
