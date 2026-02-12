# 🏢 Room Timetable Scraper Guide

## What This Does

This scraper iterates through **ALL room numbers** in your college and extracts:
- Weekly timetable for each room
- Which classes are scheduled when
- Room availability analysis
- Most/least available rooms

## Quick Start

### 1. Install Dependencies
```bash
pip install playwright python-dotenv
playwright install chromium
```

### 2. Edit Configuration

Open `room_scraper.py` and update:

```python
scraper = RoomTimetableScraper(
    user_id="YOUR_ENROLLMENT_NUMBER",  # Change this
    password="YOUR_PASSWORD",           # Change this
    fin_year="2025-26"
)
```

### 3. Configure Room Ranges

Edit the `room_ranges` in the `__init__` method to match your college's room numbering:

```python
self.room_ranges = [
    range(1001, 1020),  # Rooms 1001-1019
    range(2001, 2020),  # Rooms 2001-2019
    range(5301, 5320),  # Rooms 5301-5319 (like 5306 in video)
    # Add your college's room ranges
]
```

## Usage Modes

### Mode 1: Scrape ALL Rooms (Comprehensive)

```python
scraper = RoomTimetableScraper(
    user_id="2022UIT3042",
    password="your_password"
)

await scraper.run(mode='all', headless=False, semester="ODD")
```

**This will:**
- Check every room in your configured ranges
- Take 1-2 hours depending on number of rooms
- Save complete data for all rooms with timetables

### Mode 2: Scrape Specific Rooms (Fast)

```python
specific_rooms = [5306, 5307, 5308, 5309, 5310, 1001, 2001]

await scraper.run(
    mode='specific', 
    room_list=specific_rooms, 
    headless=False, 
    semester="ODD"
)
```

**This will:**
- Only check the rooms you specify
- Take a few minutes
- Perfect for testing or specific queries

### Mode 3: Different Semester

```python
# Scrape EVEN semester data
await scraper.run(mode='all', semester="EVEN")
```

## Output Data Structure

### File: `rooms_complete_data.json`

```json
{
  "timestamp": "2026-02-12T14:35:00",
  "user_id": "2022UIT3042",
  "total_rooms": 45,
  "analysis": {
    "total_rooms": 45,
    "most_available_rooms": [
      {
        "room": "5306",
        "availability_percentage": 87.5,
        "free_slots": 70,
        "total_slots": 80
      }
    ],
    "by_day": {
      "Mon": {"total": 400, "occupied": 250},
      "Tue": {"total": 400, "occupied": 280}
    }
  },
  "rooms": [
    {
      "room": "5306",
      "year": "2025-26",
      "schedule": {
        "Mon": [
          {
            "time_slot": "08:00-09:00",
            "content": "IT - ITTTC501 PRITI BANSAL",
            "is_occupied": true
          },
          {
            "time_slot": "09:00-10:00",
            "content": "",
            "is_occupied": false
          }
        ]
      }
    }
  ]
}
```

## Features

### ✅ Anti-Scraping Bypass
- Bypasses all debugger statements
- Handles obfuscated code
- Maintains session cookies

### ✅ Smart Iteration
- Checks all rooms in configured ranges
- Skips rooms with no data
- Progress indicator

### ✅ Availability Analysis
- Calculates availability percentage for each room
- Identifies most/least available rooms
- Breaks down by day and time slot

### ✅ Robust Error Handling
- Continues scraping even if some rooms fail
- Logs errors without stopping
- Rate limiting to avoid server overload

## Use Cases

### 1. Find Available Rooms for Events

```python
# After scraping, analyze the JSON:
import json

with open('rooms_complete_data.json') as f:
    data = json.load(f)

# Get rooms with >70% availability
available_rooms = [
    room for room in data['analysis']['most_available_rooms']
    if room['availability_percentage'] > 70
]

print("Best rooms for events:")
for room in available_rooms[:10]:
    print(f"Room {room['room']}: {room['availability_percentage']}% free")
```

### 2. Check Specific Day Availability

```python
# Find rooms free on Monday morning
for room in data['rooms']:
    schedule = room['schedule'].get('Mon', [])
    morning_slots = [s for s in schedule if '08:00' in s['time_slot'] or '09:00' in s['time_slot']]
    
    if all(not slot['is_occupied'] for slot in morning_slots):
        print(f"Room {room['room']} is free Monday morning")
```

### 3. Export to CSV for Analysis

```python
import pandas as pd

# Flatten room data
rooms_flat = []
for room in data['rooms']:
    for day, slots in room['schedule'].items():
        for slot in slots:
            rooms_flat.append({
                'room': room['room'],
                'day': day,
                'time': slot['time_slot'],
                'occupied': slot['is_occupied'],
                'content': slot['content']
            })

df = pd.DataFrame(rooms_flat)
df.to_csv('rooms_analysis.csv', index=False)
```

## Customization

### Change Time Between Requests

```python
# In scrape_all_rooms method, change:
await page.wait_for_timeout(200)  # Default: 200ms

# To:
await page.wait_for_timeout(500)  # Slower: 500ms (safer)
await page.wait_for_timeout(100)  # Faster: 100ms (riskier)
```

### Add More Room Ranges

```python
self.room_ranges = [
    range(1001, 1050),  # First floor
    range(2001, 2050),  # Second floor
    range(3001, 3050),  # Third floor
    # Lab rooms
    range(101, 150),
    # Auditoriums
    range(500, 510),
]
```

### Scrape Both Semesters

```python
# Scrape ODD semester
await scraper.run(mode='all', semester="ODD")

# Scrape EVEN semester
await scraper.run(mode='all', semester="EVEN")
```

## Performance

| Rooms | Estimated Time | Data Size |
|-------|----------------|-----------|
| 10    | 30 seconds     | ~50 KB    |
| 50    | 2-3 minutes    | ~250 KB   |
| 100   | 5-7 minutes    | ~500 KB   |
| 500   | 30-40 minutes  | ~2.5 MB   |

## Troubleshooting

### Issue: "Room input not found"
**Solution:** The portal might have changed. Update the selector:
```python
room_input = await page.query_selector('input[name="txtroom"]')
# Try different selectors if needed
```

### Issue: Scraping is slow
**Solution:** Reduce delay between requests:
```python
await page.wait_for_timeout(100)  # Faster
```

### Issue: Getting blocked
**Solution:** Increase delay:
```python
await page.wait_for_timeout(1000)  # Slower, more polite
```

### Issue: Some rooms show no data
**Normal:** Not all room numbers exist. The scraper skips them automatically.

## Best Practices

1. **Start Small**: Test with 5-10 rooms first
2. **Scrape Off-Peak**: Run during low-traffic hours
3. **Be Respectful**: Don't hammer the server
4. **Save Regularly**: The scraper auto-saves at the end
5. **Backup Data**: Keep copies of scraped JSON files

## Advanced: Schedule Automatic Scraping

```python
import schedule
import time

def scrape_job():
    scraper = RoomTimetableScraper(...)
    asyncio.run(scraper.run(mode='all', headless=True))

# Run every Monday at 2 AM
schedule.every().monday.at("02:00").do(scrape_job)

while True:
    schedule.run_pending()
    time.sleep(3600)
```

## Need Help?

Check the main README.md for:
- Installation issues
- Login problems
- General troubleshooting

---

**Ready to scrape?** Run:
```bash
python room_scraper.py
```
