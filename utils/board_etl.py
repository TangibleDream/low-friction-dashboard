import html
import re
from datetime import datetime, timedelta
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns

console = Console()

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
    return f"{date_str} {stripped}"
# utils/board_etl.py
import html
import re
from datetime import datetime, timedelta
from pathlib import Path

def complete_task(file_path: str, raw_line: str) -> None:
    path = Path(file_path)
    if not path.exists():
        print(f"[DEBUG complete_task] Path does not exist: {file_path}")
        return

    raw_text = path.read_text()
    lines = raw_text.splitlines()
    new_lines = []
    completed_block = []
    removing = False

    now = datetime.now()
    today_str = f"{now.month}/{now.day}"
    tomorrow = now + timedelta(days=1)
    tomorrow_str = f"{tomorrow.month}/{tomorrow.day}"

    # Normalize incoming string from web app/API
    target_clean = html.unescape(raw_line).strip()
    is_daily = bool(re.search(r'#daily\b', target_clean, re.IGNORECASE))

    print(f"\n--- [DEBUG complete_task] BEGIN ---")
    print(f"Incoming raw_line: {repr(raw_line)}")
    print(f"Target clean:      {repr(target_clean)}")
    print(f"is_daily detected: {is_daily}")

    # Strip #focus case-insensitively for the completed record
    clean_target = re.sub(r'\s*#focus\b', '', target_clean, flags=re.IGNORECASE)

    for line in lines:
        stripped_file_line = line.strip()
        
        # Match lines case-insensitively while ignoring extra inner whitespace
        if stripped_file_line.lower() == target_clean.lower():
            removing = True
            print(f"-> MATCH FOUND IN FILE: {repr(line)}")
            
            date_match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', clean_target)
            if not date_match:
                completed_block.append(insert_date_at_front(clean_target, today_str))
            else:
                completed_block.append(clean_target)
            continue
        
        if removing and (line.startswith(" ") or line.startswith("\t")):
            completed_block.append(stripped_file_line)
            continue
        else:
            removing = False

        new_lines.append(line)

    print(f"completed_block collected: {completed_block}")

    # Build recurring copy for tomorrow if #daily was matched
    recurring_block = []
    if is_daily:
        if not completed_block:
            print("WARNING: is_daily is True, but completed_block is empty (file line match failed!)")
        else:
            recurring_line = clean_target
            # Replace existing M/D date with tomorrow's M/D, or insert if absent
            if re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', recurring_line):
                recurring_line = re.sub(
                    r'(?<!\d:)\b\d{1,2}/\d{1,2}\b(?!\:\d{2})', 
                    tomorrow_str, 
                    recurring_line, 
                    count=1
                )
            else:
                recurring_line = insert_date_at_front(recurring_line, tomorrow_str)
            
            recurring_block.append(recurring_line)
            print(f"-> GENERATED RECURRING LINE FOR TOMORROW: {repr(recurring_line)}")

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

        final_content = "\n".join(final_lines) + "\n"
        path.write_text(final_content)
        print(f"-> FILE WRITTEN SUCCESSFULLY ({len(final_lines)} lines).")
    else:
        print("ERROR: completed_block was empty. File was NOT modified.")
    
    print(f"--- [DEBUG complete_task] END ---\n")

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
            tags = re.findall(r'#([\w-]+(?::[\w-]+)?)', content)
            
            clean_title = content
            if time_str:
                clean_title = clean_title.replace(time_str, '')
            elif date_str:
                clean_title = clean_title.replace(date_str, '')
                
            for c in contexts:
                clean_title = clean_title.replace(f'@{c}', '')
            for t in tags:
                clean_title = clean_title.replace(f'#{t}', '')
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()

            current_task = {
                'symbol': symbol,
                'title': clean_title,
                'time': time_str or date_str,
                'parsed_date': parsed_dt,
                'contexts': contexts,
                'tags': tags,
                'subtasks': [],
                'raw': stripped
            }

            if parsed_dt and parsed_dt.date() > today_date:
                future_tasks.append(current_task)
            else:
                today_tasks.append(current_task)

    future_tasks.sort(key=lambda t: t['parsed_date'] or datetime.max)

    def get_task_sort_key(t):
        if 'priority' in t['tags']:
            return 0
        if 'focus' in t['tags']:
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