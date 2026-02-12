# IMS NSIT Portal Scraper

A robust automation tool for the IMS NSIT portal, designed to bypass anti-scraping measures and extract academic data efficiently.

## 🎯 Features

This scraper defeats all modern anti-scraping measures used by the IMS portal:

- ✅ **Debugger Statement Bypass** - Disables all `debugger` calls dynamically.
- ✅ **setInterval/setTimeout Blocking** - Prevents anti-scraping timers from pausing execution.
- ✅ **Session Management** - Maintains cookies and authentication across sessions.
- ✅ **Browser Fingerprinting** - Appears as a legitimate user browser.
- ✅ **Headless Mode Support** - Can run silently in the background.

---

## 📦 Installation

### Step 1: Install Python Dependencies

```bash
pip install playwright python-dotenv pandas
```

### Step 2: Install Playwright Browsers

```bash
playwright install chromium
```

---

## 🚀 Usage

### 📊 Room Timetable Scraper (Recommended)

The main tool for scraping weekly room schedules and analyzing availability.

#### Basic Run

1. Configure your credentials in a `.env` file (see [Security](#-security)).
2. Run the scraper:

```bash
python room_scraper.py
```

#### Usage Modes

You can customize the script to run in different modes:

- **Comprehensive**: Iterate through all discovered/configured rooms.
- **Specific**: Target a list of rooms (e.g., `[5306, 5307, 5308]`).
- **Semester control**: Choose between `ODD` or `EVEN` semesters.

---

## 📈 Data Analysis

After scraping, use `analyze_rooms.py` to generate insights from the data:

```bash
python analyze_rooms.py
```

**Capabilities:**

- Find rooms with >80% availability.
- Identify peak usage hours.
- Export data to CSV (`room_analysis.csv`).
- Generate availability reports.

---

## 🛠️ Configuration

Edit `room_scraper.py` to adjust:

- **Room Ranges**: Define which room numbers to check.
- **Wait Times**: Adjust delays (default 200ms) to be more or less aggressive.
- **Headless Mode**: Toggle `headless=True/False` in the `run()` method.

---

## 🐛 Troubleshooting

| Issue                 | Solution                                                                  |
| --------------------- | ------------------------------------------------------------------------- |
| **Login fails**       | Check credentials; ensure captcha is solved correctly in the browser.     |
| **Debugger triggers** | The script handles this, but ensure `bypass_all_protections()` is active. |
| **Page not loading**  | Increase `wait_for_load_state` timeout in the code.                       |
| **No data found**     | Normal for non-existent rooms; the scraper will skip them automatically.  |

---

## 🔒 Security

**NEVER** commit your credentials to version control.

1. Create a `.env` file in the project root:
   ```env
   IMS_USER_ID=2022UIT3042
   IMS_PASSWORD=your_password
   ```
2. The scraper will automatically load these.
3. Ensure `.env` is in your `.gitignore`.

---

## 📝 License

For educational purposes only. Use responsibly and respect the portal's rate limits.
