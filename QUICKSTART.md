# 🚀 Quick Start Guide

## Anti-Scraping Measures Identified in Your IMS Portal

Based on the video analysis, your portal uses these protections:

1. **Debugger Statements** - `debugger` calls that pause execution
2. **setInterval Anti-Debug** - Continuous debugger triggers every 300ms
3. **Obfuscated Code** - Files like `content-main.js` with random parameters
4. **UUID Token Generation** - Custom crypto tokens for requests
5. **Session Management** - Cookie-based authentication
6. **robots.txt** - Blocks automated crawlers

## How This Scraper Defeats Them

✅ **Playwright** - Real browser automation (not blocked like requests/curl)
✅ **Debugger Override** - Replaces `debugger` function with empty function
✅ **Interval Blocking** - Intercepts and blocks anti-debug setInterval calls
✅ **Browser Fingerprinting** - Appears as real Chrome browser
✅ **Session Handling** - Maintains cookies automatically

## Installation (5 minutes)

```bash
# 1. Install Python packages
pip install -r requirements.txt

# 2. Install Chromium browser
playwright install chromium
```

## Usage (First Time)

### Option 1: Advanced Scraper (Recommended)

```bash
python advanced_scraper.py
```

**What happens:**

1. Browser opens (visible)
2. Navigates to IMS portal
3. Fills in your credentials (edit the script first!)
4. **PAUSES for you to solve captcha**
5. Logs in after you press Enter
6. **PAUSES for you to navigate to room allocation**
7. Scrapes all data
8. Saves to JSON file

### Option 2: Basic Scraper

```bash
python ims_scraper.py
```

## Configuration

### Edit the script with your credentials:

```python
scraper = AdvancedIMSScraper(
    user_id="2022UIT3042",  # Change this!
    password="vogsue-7",          # Change this!
    fin_year="2025-26"
)
```

### Or use environment variables (more secure):

1. Copy `.env.example` to `.env`
2. Edit `.env` with your credentials
3. Scraper will auto-load them

## First Run Checklist

- [ ] Edit `advanced_scraper.py` and add your credentials
- [ ] Run the script: `python advanced_scraper.py`
- [ ] Solve captcha when prompted
- [ ] Navigate to room allocation when prompted
- [ ] Check output: `ims_room_data.json`

## Output Files

After running, you'll get:

1. **ims_room_data.json** - All scraped data
2. **after_login_TIMESTAMP.png** - Screenshot after login
3. **room_allocation_page_TIMESTAMP.png** - Screenshot of data page

## Customization

Once you see what data is available, you can customize the extraction logic in `scrape_table_data()` and `scrape_custom_data()` functions.

## Common Issues

### "Login failed"

- Check credentials
- Make sure captcha was solved correctly

### "Debugger still triggering"

- Close and reopen browser
- Script automatically handles this

### "Can't find room allocation link"

- Use manual navigation mode (default)
- Or update selectors in the code

## Next Steps

1. **Automate captcha** - Use 2Captcha API (instructions in README.md)
2. **Schedule scraping** - Run hourly/daily (instructions in README.md)
3. **Export to CSV/Excel** - Add pandas export (examples in README.md)
4. **Build a dashboard** - Use the JSON data with any visualization tool

## Help

- Full documentation: `README.md`
- Basic scraper: `ims_scraper.py`
- Advanced scraper: `advanced_scraper.py`

## Security Note

**NEVER** commit your credentials to Git!

```bash
# Add to .gitignore
echo ".env" >> .gitignore
echo "*.json" >> .gitignore
```

---

**Ready?** Run `python advanced_scraper.py` and you're good to go! 🎉
