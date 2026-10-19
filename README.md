# ⚡ Executive Focus Engine

A minimalist, high-intent task management dashboard engineered to maintain focus, eliminate visual clutter, and facilitate single-task execution. Built with **Python 3.12**, **Flask**, **Bootstrap 5**, and **Server-Sent Events (SSE)** for instant live syncing.

---

## 🎯 Design Philosophy

The Executive Focus Engine treats your local `tasks.txt` file as the single source of truth. Tasks are structured using low-friction shorthand syntax (`!`, `*`, `?`, `#tags`, `@context`) and dynamically parsed into an actionable single-task schedule.

- **Primary Focus Layer:** Keeps your active workload clear by displaying top-tier priorities first.
- **Dynamic Action Grouping:** Select any task to bring it into active focus, shift it to tomorrow, mark it complete, move non-priority items to the bottom, or export it directly to your calendar.
- **Calendar Native:** Generate RFC 5545-compliant `.ics` files for scheduled timed events compatible with Microsoft Outlook, Apple Calendar, and Google Calendar.

---

## 🛠️ Tech Stack & Directory Layout

```text
low-friction-dashboard/
├── features/            # BDD feature specifications (.feature files)
├── utils/               # Internal ETL engines & utility modules
│   ├── board_etl.py     # Parsing and file manipulation
│   └── ics_utils.py     # iCalendar RFC 5545 exporter
├── tests/               # Pytest suite & BDD step definitions
│   ├── test_etl.py
│   └── test_ics.py
├── tasks.txt            # Local plain-text task data store
├── web_app.py           # Flask server & SSE streaming engine
├── requirements.txt     # Python dependencies
└── pytest.ini           # Pytest import & environment config
```
🚀 Quickstart & Environment Setup
Prerequisites
pyenv (recommended for Python version management)

Git

1. Clone the Repository

```
git clone [https://github.com/TangibleDream/low-friction-dashboard.git](https://github.com/TangibleDream/low-friction-dashboard.git)
cd low-friction-dashboard
```
2. Set Up Python with pyenv
Ensure you have Python 3.12+ installed via pyenv:
```
# Install Python 3.12 if not already present
pyenv install 3.12.0

# Set local directory Python version
pyenv local 3.12.0
```
3. Create & Activate a Virtual Environment
```
# Create virtual environment
python -m venv .venv

# Activate environment
# On macOS/Linux:
source .venv/bin/activate
# On Windows:
# .venv\Scripts\activate
```
4. Install Dependencies
```
pip install --upgrade pip
pip install -r requirements.txt
```
💻 Running the Application
Start the local Flask dashboard server:
```
python web_app.py
```
Open your browser and navigate to:

[http://127.0.0.1:5000](http://127.0.0.1:5000)

Note: Changes made directly to tasks.txt will automatically push real-time updates to the dashboard via Server-Sent Events (SSE) without requiring a full page refresh.

🧪 Running Tests
Execute the full unit test and BDD test suite:
```
pytest
```

## Recurring Task Engine

The task engine automatically spawns a future-dated copy of any task completed in the UI when tagged with a recurrence rule. Completed instances are logged under `# Done` while their recurring counterpart is scheduled forward.

### Supported Recurrence Tags

| Tag | Recurrence Rule | Example | Next Date (if completed 10/18) |
| :--- | :--- | :--- | :--- |
| `#Daily` | Spawns task for tomorrow | `* Walk 11K steps #Daily` | `10/19` |
| `#Weekdays` | Spawns for tomorrow (Mon–Thu) or next Monday (Fri–Sat) | `* Submit status report #Weekdays` | `10/19` (from Sun) / `10/26` (from Fri) |
| `#X-Days` | Spawns $X$ days into the future | `* Clean water filter #14-Days` | `11/01` |
| `#Monthly` | Spawns exactly 1 month ahead | `* Pay rent #Monthly` | `11/18` |
| `#<Nth>-<Weekday>` | Spawns for the $N^{\text{th}}$ ordinal weekday of next month | `* Board meeting #3rd-Sunday` | `11/15` |

#### Ordinal Weekday Formats
- **Ordinals:** `#1st`, `#2nd`, `#3rd`, `#4th`, `#5th`
- **Weekdays:** `-Monday`, `-Tuesday`, `-Wednesday`, `-Thursday`, `-Friday`, `-Saturday`, `-Sunday`
- **Examples:** `#1st-Monday`, `#2nd-Friday`, `#3rd-Sunday`, `#4th-Thursday`
---

📝 Syntax Reference for `tasks.txt`

 |Symbol / Tag|Meaning|Example|
 |---|---|---|
 |!|Strong Commitment|! 10/16 10:00 Walk 11K steps #daily|
 |*|Fluid Task|* Review pull requests #work| 
 |?|Arbitrary / Optional|? Explore 48-TET microtonal tuning| 
 |#priority|Anchors task to top of active schedule|* 10/16 Prepare presentation #priority|
 |#focus|Marks task as currently selected|! 10/16 Write documentation #focus|
 |@context|Context tag|(e.g., `@home`, `@admin`, `@logistics`)|