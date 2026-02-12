# IMS NSIT Portal Scraper

## 🎯 Features

This scraper bypasses all anti-scraping measures used by the IMS portal:

- ✅ **Debugger Statement Bypass** - Disables all `debugger` calls
- ✅ **setInterval Blocking** - Prevents anti-scraping timers
- ✅ **Session Management** - Maintains cookies and authentication
- ✅ **Browser Fingerprinting** - Appears as a real browser
- ✅ **Headless Mode** - Can run without visible browser

## 📦 Installation

### Step 1: Install Python Dependencies

```bash
pip install playwright
```

### Step 2: Install Playwright Browsers

```bash
playwright install chromium
```

## 🚀 Usage

### Basic Usage

```python
from ims_scraper import IMSScraper
import asyncio

async def main():
    scraper = IMSScraper(
        user_id="2022UIT3042",      # Your enrollment number
        password="your_password",    # Your password
        fin_year="2025-26"          # Financial year
    )
    
    # Run with visible browser (easier for first time)
    await scraper.run(headless=False)

asyncio.run(main())
```

### Run the Script

```bash
python ims_scraper.py
```

## 🔧 Customization

### 1. Finding Room Allocation Link

You need to update the `navigate_to_room_allocation()` method with the correct selector:

```python
async def navigate_to_room_allocation(self, page):
    # Replace with actual link text or selector
    await page.click('text="Room Allocation"')  # Example
    # OR
    await page.click('a[href*="room"]')  # Example
```

### 2. Extracting Specific Data

Update the `scrape_room_data()` method to extract the exact fields you need:

```python
async def scrape_room_data(self, page):
    room_data = await page.evaluate("""
        () => {
            const rooms = [];
            
            // Example: Extract from a specific table
            document.querySelectorAll('table.room-table tr').forEach(row => {
                const cells = row.querySelectorAll('td');
                if (cells.length >= 3) {
                    rooms.push({
                        room_number: cells[0].textContent.trim(),
                        capacity: cells[1].textContent.trim(),
                        status: cells[2].textContent.trim()
                    });
                }
            });
            
            return rooms;
        }
    """)
    
    return room_data
```

### 3. Automated Captcha Solving

For automated captcha solving, you can integrate:

**Option A: 2Captcha** (paid but reliable)
```python
pip install 2captcha-python

from twocaptcha import TwoCaptcha

solver = TwoCaptcha('YOUR_API_KEY')
result = solver.normal('captcha.jpg')
captcha_text = result['code']
```

**Option B: Tesseract OCR** (free but less accurate)
```python
pip install pytesseract pillow

import pytesseract
from PIL import Image

# Screenshot captcha
await page.screenshot(path='captcha.png', clip={...})
captcha_text = pytesseract.image_to_string(Image.open('captcha.png'))
```

## 🛠️ Advanced Features

### Schedule Automatic Scraping

```python
import schedule
import time

def job():
    asyncio.run(scraper.run(headless=True))

# Run every hour
schedule.every(1).hours.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
```

### Save to Database

```python
import sqlite3

async def save_to_db(self, data):
    conn = sqlite3.connect('ims_data.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY,
            timestamp TEXT,
            room_number TEXT,
            capacity INTEGER,
            status TEXT
        )
    ''')
    
    for room in data:
        cursor.execute('''
            INSERT INTO rooms (timestamp, room_number, capacity, status)
            VALUES (?, ?, ?, ?)
        ''', (datetime.now().isoformat(), room['room_number'], 
              room['capacity'], room['status']))
    
    conn.commit()
    conn.close()
```

### Export to CSV

```python
import pandas as pd

async def save_to_csv(self, data):
    df = pd.DataFrame(data)
    df.to_csv('/mnt/user-data/outputs/rooms.csv', index=False)
```

## 🐛 Troubleshooting

### Issue: Debugger still triggers
**Solution:** Make sure `bypass_debugger()` is called on every page load:

```python
await page.goto(url)
await self.bypass_debugger(page)
```

### Issue: Login fails
**Solution:** Check if captcha needs solving. The script pauses for manual entry.

### Issue: Page not loading
**Solution:** Increase wait time:

```python
await page.wait_for_load_state('networkidle', timeout=30000)
```

### Issue: Data extraction fails
**Solution:** Inspect the HTML structure and update selectors:

```python
# Take screenshot to debug
await page.screenshot(path='debug.png')

# Print HTML
html = await page.content()
print(html)
```

## 📊 Output Format

Data is saved as JSON:

```json
{
  "timestamp": "2026-02-12T14:10:00",
  "user_id": "2022UIT3042",
  "data": [
    ["Room", "Capacity", "Status"],
    ["101", "50", "Available"],
    ["102", "40", "Occupied"]
  ]
}
```

## ⚠️ Important Notes

1. **Respect the Portal**: Don't hammer the server with too many requests
2. **Rate Limiting**: Add delays between requests
3. **Session Management**: Sessions expire, you may need to re-login
4. **Captcha**: Manual solving is most reliable for occasional use
5. **Legal**: Use only for legitimate purposes with your own credentials

## 🔒 Security

- **Never commit your credentials** to version control
- Use environment variables:

```python
import os

scraper = IMSScraper(
    user_id=os.getenv('IMS_USER_ID'),
    password=os.getenv('IMS_PASSWORD')
)
```

## 📝 License

For educational purposes only. Use responsibly.
