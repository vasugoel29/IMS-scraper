"""
IMS NSIT Portal Scraper
Bypasses debugger statements, obfuscated code, and session management
"""

import asyncio
from playwright.async_api import async_playwright
import json
from datetime import datetime
import os

class IMSScraper:
    def __init__(self, user_id: str, password: str, fin_year: str = "2025-26"):
        self.user_id = user_id
        self.password = password
        self.fin_year = fin_year
        self.base_url = "https://www.imsnsit.org/imsnsit/"
        
    async def bypass_debugger(self, page):
        """
        Bypass debugger statements by overriding the debugger function
        and disabling setInterval that triggers debuggers
        """
        await page.evaluate("""
            // Override debugger statement to do nothing
            window.debugger = function() {};
            
            // Store original setInterval
            const originalSetInterval = window.setInterval;
            
            // Override setInterval to block debugger-related intervals
            window.setInterval = function(callback, delay, ...args) {
                const callbackStr = callback.toString();
                // Block any interval that contains 'debugger' or 'dbg'
                if (callbackStr.includes('debugger') || 
                    callbackStr.includes('dbg') ||
                    callbackStr.includes('OffFF')) {
                    console.log('Blocked anti-scraping interval');
                    return -1;
                }
                return originalSetInterval(callback, delay, ...args);
            };
            
            // Clear any existing debugger intervals
            for (let i = 0; i < 10000; i++) {
                clearInterval(i);
            }
            
            console.log('Debugger bypass activated');
        """)
    
    async def login(self, page):
        """
        Navigate to login page and authenticate
        """
        print("🔐 Navigating to login page...")
        await page.goto(self.base_url, wait_until='networkidle')
        
        # Click Student Login
        await page.click('input[value="Student Login"]')
        await page.wait_for_load_state('networkidle')
        
        # Apply debugger bypass
        await self.bypass_debugger(page)
        
        print(f"📝 Logging in as {self.user_id}...")
        
        # Fill login form
        await page.fill('input[name="txtuserid"]', self.user_id)
        await page.fill('input[name="txtpassword"]', self.password)
        await page.select_option('select[name="cmbfinyear"]', self.fin_year)
        
        # Get and solve captcha (you'll need to handle this)
        # For now, we'll wait for manual captcha entry
        print("⏳ Please solve the captcha manually in the browser...")
        print("   Press Enter in terminal after solving captcha...")
        
        # Wait for user to press enter
        await asyncio.get_event_loop().run_in_executor(None, input)
        
        # Click login button
        await page.click('input[value="Login"]')
        
        # Wait for navigation after login
        await page.wait_for_load_state('networkidle')
        
        # Apply debugger bypass again after navigation
        await self.bypass_debugger(page)
        
        print("✅ Login successful!")
        
    async def navigate_to_room_allocation(self, page):
        """
        Navigate to the room allocation page
        """
        print("🏢 Navigating to room allocation...")
        
        # Click on "My Activities" or navigate to room allocation
        # You'll need to identify the exact link/button from your portal
        # For now, let's try to find it
        
        # Wait a bit for page to stabilize
        await asyncio.sleep(2)
        
        # Apply debugger bypass
        await self.bypass_debugger(page)
        
        # Look for room allocation link - adjust selector as needed
        # This is a placeholder - you need to find the actual selector
        try:
            # Try common patterns
            await page.click('text=/room.*allocation/i', timeout=5000)
        except:
            print("⚠️  Could not find room allocation link automatically")
            print("   Please click it manually and press Enter...")
            await asyncio.get_event_loop().run_in_executor(None, input)
        
        await page.wait_for_load_state('networkidle')
        await self.bypass_debugger(page)
        
    async def scrape_room_data(self, page):
        """
        Extract room availability data from the page
        """
        print("📊 Scraping room data...")
        
        # Apply debugger bypass one more time
        await self.bypass_debugger(page)
        
        # Extract data - adjust selectors based on actual HTML structure
        room_data = await page.evaluate("""
            () => {
                const data = [];
                
                // Find tables or divs containing room data
                // This is a generic example - adjust based on actual structure
                const tables = document.querySelectorAll('table');
                
                tables.forEach(table => {
                    const rows = table.querySelectorAll('tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td, th');
                        if (cells.length > 0) {
                            const rowData = Array.from(cells).map(cell => cell.textContent.trim());
                            data.push(rowData);
                        }
                    });
                });
                
                return data;
            }
        """)
        
        return room_data
    
    async def save_data(self, data, filename='room_data.json'):
        """
        Save scraped data to JSON file
        """
        output = {
            'timestamp': datetime.now().isoformat(),
            'user_id': self.user_id,
            'data': data
        }
        
        output_path = f'/mnt/user-data/outputs/{filename}'
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=2)
        
        print(f"💾 Data saved to {filename}")
        
    async def run(self, headless=False):
        """
        Main scraping workflow
        """
        async with async_playwright() as p:
            # Launch browser - headless=False lets you see what's happening
            browser = await p.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',  # Hide automation
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            # Create context with realistic browser fingerprint
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Hide webdriver property
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page = await context.new_page()
            
            try:
                # Login
                await self.login(page)
                
                # Navigate to room allocation
                await self.navigate_to_room_allocation(page)
                
                # Scrape data
                room_data = await self.scrape_room_data(page)
                
                # Save data
                await self.save_data(room_data)
                
                print("\n✨ Scraping completed successfully!")
                print(f"📈 Extracted {len(room_data)} records")
                
                # Keep browser open for inspection
                if not headless:
                    print("\n🔍 Browser kept open for inspection. Close it to exit.")
                    await page.pause()
                
            except Exception as e:
                print(f"❌ Error during scraping: {e}")
                import traceback
                traceback.print_exc()
                
            finally:
                await browser.close()


# Example usage
async def main():
    scraper = IMSScraper(
        user_id="2022UIT3042",  # Replace with your ID
        password="your_password",  # Replace with your password
        fin_year="2025-26"
    )
    
    # Run with headless=False to see the browser
    await scraper.run(headless=False)


if __name__ == "__main__":
    asyncio.run(main())
