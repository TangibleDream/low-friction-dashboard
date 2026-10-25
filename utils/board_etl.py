import calendar
import html
import re
from datetime import datetime, timedelta
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns

console = Console()

def complete_task(file_path: str, raw_line: str) -> None:
    path = Path(file_path)
    if not path.exists():
        return

    lines = path.read_text().splitlines()
    new_lines = []
    completed_block = []
    removing = False

    now = datetime.now()
    today_str = f"{now.month}/{now.day}"

    target_clean = html.unescape(raw_line).strip()

    # Determine recurrence target date
    next_dt = None

    # 1. Check #not-<weekday> (e.g. #Not-Sunday, #Not-Friday)
    not_wday_match = re.search(
        r'#not-(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', 
        target_clean, 
        re.IGNORECASE
    )

    if not_wday_match:
        wday_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        excluded_wday = wday_map[not_wday_match.group(1).lower()]
        candidate_dt = now + timedelta(days=1)
        if candidate_dt.weekday() == excluded_wday:
            candidate_dt += timedelta(days=1)
        next_dt = candidate_dt

    # 2. Check #nth-weekday pattern (e.g. #1st-Monday, #3rd-Sunday)
    elif re.search(
        r'#(1st|2nd|3rd|4th|5th)-(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', 
        target_clean, 
        re.IGNORECASE
    ):
        nth_match = re.search(
            r'#(1st|2nd|3rd|4th|5th)-(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b', 
            target_clean, 
            re.IGNORECASE
        )
        ord_map = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5}
        wday_map = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6
        }
        ordinal = ord_map[nth_match.group(1).lower()]
        target_wday = wday_map[nth_match.group(2).lower()]
        next_dt = get_nth_weekday_of_next_month(now, ordinal, target_wday)

    # 3. Check #monthly
    elif re.search(r'#monthly\b', target_clean, re.IGNORECASE):
        next_dt = get_next_month_date(now)

    # 4. Check #weekdays
    elif re.search(r'#weekdays\b', target_clean, re.IGNORECASE):
        current_wday = now.weekday()
        days_offset = 3 if current_wday == 4 else (2 if current_wday == 5 else 1)
        next_dt = now + timedelta(days=days_offset)

    # 5. Check #daily
    elif re.search(r'#daily\b', target_clean, re.IGNORECASE):
        next_dt = now + timedelta(days=1)

    # 6. Check #X-days
    else:
        x_days_match = re.search(r'#(\d+)-days?\b', target_clean, re.IGNORECASE)
        if x_days_match:
            next_dt = now + timedelta(days=int(x_days_match.group(1)))

    # Strip #focus case-insensitively
    clean_target = re.sub(r'\s*#focus\b', '', target_clean, flags=re.IGNORECASE)

    for line in lines:
        if line.strip().lower() == target_clean.lower():
            removing = True
            
            date_match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', clean_target)
            if not date_match:
                completed_block.append(insert_date_at_front(clean_target, today_str))
            else:
                completed_block.append(clean_target)
            continue
        
        if removing and (line.startswith(" ") or line.startswith("\t")):
            completed_block.append(line.strip())
            continue
        else:
            removing = False

        new_lines.append(line)

    # Build recurring copy for calculated target date
    recurring_block = []
    if next_dt is not None and completed_block:
        next_date_str = f"{next_dt.month}/{next_dt.day}"

        recurring_line = clean_target
        if re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', recurring_line):
            recurring_line = re.sub(
                r'(?<!\d:)\b\d{1,2}/\d{1,2}\b(?!\:\d{2})', 
                next_date_str, 
                recurring_line, 
                count=1
            )
        else:
            recurring_line = insert_date_at_front(recurring_line, next_date_str)
        
        recurring_block.append(recurring_line)

    if completed_block:
        done_idx = None
        for idx, line in enumerate(new_lines):
            if line.strip() == "# Done":
                done_idx = idx
                break

        if done_idx is not None:
            final_lines = new_lines[:done_idx] + recurring_block + new_lines[done_idx:]
        else:
            final_lines = new_lines + recurring_block

        if "# Done" not in final_lines:
            final_lines.append("\n# Done")

        for item in completed_block:
            clean_item = re.sub(r'^(?:x\s*)+', '', item)
            final_lines.append(f"x {clean_item}")

        path.write_text("\n".join(final_lines) + "\n")

def delete_line(file_path: str, raw_line: str) -> None:
    path = Path(file_path)
    if not path.exists():
        return

    lines = path.read_text().splitlines()
    new_lines = []
    deleting = False
    target_clean = raw_line.strip()

    for line in lines:
        if line.strip() == target_clean:
            deleting = True
            continue

        if deleting:
            if line.startswith(" ") or line.startswith("\t"):
                continue
            else:
                deleting = False

        new_lines.append(line)

    path.write_text("\n".join(new_lines) + "\n")

def get_next_month_date(base_date: datetime) -> datetime:
    """Calculates the same calendar day in the following month (handling month-end overflows)."""
    month = base_date.month % 12 + 1
    year = base_date.year + (base_date.month // 12)
    max_days = calendar.monthrange(year, month)[1]
    day = min(base_date.day, max_days)
    return datetime(year, month, day)

def get_nth_weekday_of_next_month(base_date: datetime, ordinal: int, target_weekday: int) -> datetime:
    """
    Finds the Nth occurrence (1-5) of target_weekday (0=Monday..6=Sunday) in the next month.
    If the 5th occurrence doesn't exist, falls back to the final matching weekday of that month.
    """
    next_m = base_date.month % 12 + 1
    year = base_date.year + (base_date.month // 12)
    
    # Collect all matching weekdays in the target month
    cal = calendar.Calendar(firstweekday=0)
    matching_days = [
        day for day, wday in cal.itermonthdays2(year, next_m)
        if day != 0 and wday == target_weekday
    ]
    
    target_day = matching_days[ordinal - 1] if len(matching_days) >= ordinal else matching_days[-1]
    return datetime(year, next_m, target_day)

def insert_date_at_front(raw_line: str, date_str: str) -> str:
    """
    Inserts date_str right after the task symbol (!, *, ?), or at the beginning 
    if no symbol is present.
    Example: "* Dry Whites" -> "* 10/17 Dry Whites"
    """
    stripped = raw_line.strip()
    if stripped and stripped[0] in "!*?":
        symbol = stripped[0]
        content = stripped[1:].strip()
        return f"{symbol} {date_str} {content}"
    return f"{date_str} {stripped}"# utils/board_etl.py

def make_line_today(raw_line: str) -> str:
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"
    
    date_match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', raw_line)
    if date_match:
        return raw_line[:date_match.start(1)] + today_str + raw_line[date_match.end(1):]
        
    return f"{raw_line.strip()} {today_str}"

def move_line_to_bottom(file_path: str, raw_line: str) -> None:
    path = Path(file_path)
    if not path.exists():
        return

    lines = path.read_text().splitlines()
    new_lines = []
    task_block = []
    collecting = False

    target_clean = raw_line.strip()

    for line in lines:
        if line.strip() == target_clean:
            collecting = True
            clean_line = re.sub(r'\s*#focus\b', '', line)
            task_block.append(clean_line)
            continue

        if collecting:
            if line.startswith(" ") or line.startswith("\t"):
                task_block.append(line)
                continue
            else:
                collecting = False

        new_lines.append(line)

    if task_block:
        done_idx = None
        for idx, line in enumerate(new_lines):
            if line.strip() == "# Done":
                done_idx = idx
                break

        if done_idx is not None:
            final_lines = new_lines[:done_idx] + task_block + [""] + new_lines[done_idx:]
        else:
            final_lines = new_lines + [""] + task_block

        path.write_text("\n".join(final_lines) + "\n")

def parse_date(content_str):
    if not content_str:
        return None
    
    match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', content_str)
    if match:
        month, day = map(int, match.group(1).split('/'))
        now = datetime.now()
        target_year = now.year
        if now.month == 12 and month == 1:
            target_year += 1
        try:
            return datetime(target_year, month, day)
        except ValueError:
            return None
    return None

def parse_tasks(file_path: str):
    today_tasks = []
    future_tasks = []
    completed_tasks = []
    
    if not Path(file_path).exists():
        return {"today": today_tasks, "future": future_tasks, "completed": completed_tasks, "all_tags": []}

    current_task = None
    in_done_section = False
    today_date = datetime.now().date()

    with open(file_path, "r") as f:
        for line in f:
            raw_line = line.rstrip()
            stripped = raw_line.strip()

            if not stripped:
                continue

            if stripped.startswith("# Done"):
                in_done_section = True
                continue

            if stripped.startswith("x ") or (in_done_section and not (stripped and stripped[0] in "!*?-0123456789")):
                clean_done = re.sub(r'^(?:x\s*)+', '', stripped)
                clean_done = re.sub(r'^\*\s*', '', clean_done)
                if clean_done:
                    completed_tasks.append(clean_done)
                continue

            if stripped.startswith("# "):
                continue

            if raw_line.startswith(" ") or raw_line.startswith("\t"):
                if current_task is not None and not in_done_section:
                    sub_title = re.sub(r'^\*\s*', '', stripped)
                    current_task['subtasks'].append(sub_title)
                continue

            # Handle explicit dates or hyphen bullets gracefully
            first_char = stripped[0]
            if first_char in "!*?":
                symbol = first_char
                content = stripped[1:].strip()
            elif first_char in "-0123456789":
                symbol = "*"
                content = stripped.lstrip("- ").strip()
            else:
                continue

            in_done_section = False

            parsed_dt = parse_date(content)

            time_match = re.search(
                r'\b((?:\d{1,2}/\d{1,2}\s+)?\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)\b', 
                content
            )
            time_str = time_match.group(1) if time_match else None
            
            date_match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', content)
            date_str = date_match.group(1) if date_match else None

            contexts = re.findall(r'@([\w-]+)', content)
            raw_tags = re.findall(r'#([\w-]+(?::[\w-]+)?)', content)
            tags = [t.lower() for t in raw_tags]

            # Extract fibonacci score if present (e.g., #fib:3 -> '3')
            fib_score = None
            for tag in tags:
                if tag.startswith("fib:"):
                    fib_score = tag.split(":", 1)[1]
                    break

            contexts = re.findall(r'@([\w-]+)', content)

            clean_title = content
            if time_str:
                clean_title = clean_title.replace(time_str, '')
            elif date_str:
                clean_title = clean_title.replace(date_str, '')

            # Strip contexts and tags case-insensitively
            for c in contexts:
                clean_title = re.sub(rf'@{re.escape(c)}\b', '', clean_title, flags=re.IGNORECASE)
            # Ensure fib: tags are stripped from the main title text
            for t in raw_tags:
                clean_title = re.sub(rf'#{re.escape(t)}\b', '', clean_title, flags=re.IGNORECASE)

            clean_title = re.sub(r'\s+', ' ', clean_title).strip()

            # Include 'fib_score' in current_task dictionary:
            current_task = {
                'symbol': symbol,
                'title': clean_title,
                'time': time_str or date_str,
                'parsed_date': parsed_dt,
                'contexts': contexts,
                'tags': tags,
                'fib_score': fib_score,
                'subtasks': [],
                'raw': stripped
            }

            if parsed_dt and parsed_dt.date() > today_date:
                future_tasks.append(current_task)
            else:
                today_tasks.append(current_task)

    future_tasks.sort(key=lambda t: t['parsed_date'] or datetime.max)

    def get_task_sort_key(t):
        lower_tags = [tag.lower() for tag in t.get('tags', [])]
        if 'priority' in lower_tags:
            return 0
        if 'focus' in lower_tags:
            return 1
        return 2

    today_tasks.sort(key=get_task_sort_key)

    all_tags = set()
    path = Path(file_path)
    if path.exists():
        found = re.findall(r'#([a-zA-Z0-9_\-]+)', path.read_text())
        for t in found:
            if t not in ('focus', 'priority'):
                all_tags.add(t)

    return {
        "today": today_tasks,
        "future": future_tasks,
        "completed": completed_tasks,
        "all_tags": sorted(list(all_tags))
    }

def render_dashboard(data):
    """Renders a Rich terminal view of today's schedule structure and task panels."""
    if isinstance(data, dict):
        tasks = data.get("today", [])
        future = data.get("future", [])
    else:
        tasks = data
        future = []

    console.clear()
    console.print(Panel("[bold cyan]ADHD Executive Focus Engine[/bold cyan]", expand=False))

    timeline_table = Table(title="[bold]Today's Schedule Structure[/bold]", show_header=True, header_style="bold magenta")
    timeline_table.add_column("Type", style="dim", width=12)
    timeline_table.add_column("Time / Date", width=18)
    timeline_table.add_column("Context", width=12)
    timeline_table.add_column("Task")

    for t in tasks:
        ctx_str = f"@{t['contexts'][0]}" if t['contexts'] else ""
        task_display = f"[bold]{t['title']}[/bold]" if t['symbol'] == '!' else t['title']
        if t['subtasks']:
            for sub in t['subtasks']:
                task_display += f"\n  [dim]↳ {sub}[/dim]"

        if t['symbol'] == '!':
            timeline_table.add_row("[bold red]STRONG[/bold red]", t['time'] or "Today", ctx_str, task_display)
        elif t['symbol'] == '?':
            timeline_table.add_row("[dim yellow]ARBITRARY[/dim yellow]", t['time'] or "Flexible", ctx_str, f"[italic dim]{task_display}[/italic dim]")
        elif t['symbol'] == '*':
            timeline_table.add_row("[cyan]FLUID[/cyan]", t['time'] or "Flexible", ctx_str, task_display)

    quick_tasks = [f"• {t['title']}" for t in tasks if 'quick' in t['tags'] or 'low_energy' in t['tags']]
    waiting_tasks = [
        f"• {t['title']} [dim]({' '.join(f'#{tag}' for tag in t['tags'])})[/dim]"
        for t in tasks if any(tag == 'wait' or tag.startswith('wait:') for tag in t['tags'])
    ]

    quick_panel = Panel(
        "\n".join(quick_tasks) if quick_tasks else "[dim]None logged[/dim]",
        title="⚡ Low-Hanging Fruit (<15m / Low Energy)",
        border_style="green"
    )
    
    waiting_panel = Panel(
        "\n".join(waiting_tasks) if waiting_tasks else "[dim]None logged[/dim]",
        title="⏳ Gap Fillers (While Waiting on Main Task)",
        border_style="yellow"
    )

    console.print(timeline_table)
    if future:
        future_text = "\n".join(f"• [{t['time'] or 'Future'}] {t['title']}" for t in future[:3])
        if len(future) > 3:
            future_text += f"\n[dim]...and {len(future) - 3} more[/dim]"
        console.print(Panel(future_text, title=f"📅 Future Tasks ({len(future)} Scheduled)", border_style="cyan"))

    console.print(Columns([quick_panel, waiting_panel]))

def shift_line_to_tomorrow(raw_line: str) -> str:
    now = datetime.now()
    today_date = now.date()
    tomorrow_date = today_date + timedelta(days=1)
    
    date_match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', raw_line)
    
    if date_match:
        month, day = map(int, date_match.group(1).split('/'))
        try:
            current_dt = datetime(now.year, month, day).date()
            next_dt = current_dt + timedelta(days=1)
            new_date_str = f"{next_dt.month}/{next_dt.day}"
            return raw_line[:date_match.start(1)] + new_date_str + raw_line[date_match.end(1):]
        except ValueError:
            pass
            
    tomorrow_str = f"{tomorrow_date.month}/{tomorrow_date.day}"
    return f"{raw_line.strip()} {tomorrow_str}"

def toggle_line_focus(file_path: str, raw_line: str) -> None:
    path = Path(file_path)
    if not path.exists():
        return

    lines = path.read_text().splitlines()
    new_lines = []
    target_clean = raw_line.strip()
    is_currently_focused = '#focus' in target_clean

    for line in lines:
        stripped = line.strip()
        cleared_line = re.sub(r'\s*#focus\b', '', line)

        if stripped == target_clean:
            if not is_currently_focused:
                new_lines.append(f"{cleared_line.rstrip()} #focus")
            else:
                new_lines.append(cleared_line)
        else:
            new_lines.append(cleared_line)

    path.write_text("\n".join(new_lines) + "\n")