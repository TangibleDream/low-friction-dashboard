import re
from datetime import datetime, timedelta  # <-- Add timedelta here
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns

console = Console()

def parse_date(content_str):
    """
    Parses explicit date shorthands like '10/5' or '10/5 4:30' from line content.
    Prevents time ranges like '10:30 - 11:00' from being falsely parsed as '10/30'.
    """
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
        return {"today": today_tasks, "future": future_tasks, "completed": completed_tasks}

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

            if stripped.startswith("x ") or (in_done_section and not (stripped and stripped[0] in "!*?")):
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

            symbol = stripped[0]
            if symbol not in "!*?":
                continue

            in_done_section = False

            content = stripped[1:].strip()

            parsed_dt = parse_date(content)

            # Match time or date+time string
            time_match = re.search(
                r'\b((?:\d{1,2}/\d{1,2}\s+)?\d{1,2}:\d{2}(?:\s*-\s*\d{1,2}:\d{2})?)\b', 
                content
            )
            time_str = time_match.group(1) if time_match else None
            
            # Match standalone date (e.g. "10/5") if no full time string matched
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

    # Sort future tasks chronologically
    future_tasks.sort(key=lambda t: t['parsed_date'] or datetime.max)

    # Sorting Hierarchy for Today's Tasks:
    # 0 -> #priority tasks (highest precedence)
    # 1 -> #focus task (floats right below priority items)
    # 2 -> Standard tasks
    def get_task_sort_key(t):
        if 'priority' in t['tags']:
            return 0
        if 'focus' in t['tags']:
            return 1
        return 2

    today_tasks.sort(key=get_task_sort_key)

    return {
        "today": today_tasks,
        "future": future_tasks,
        "completed": completed_tasks
    }

def render_dashboard(data):
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

    quick_tasks = []
    waiting_tasks = []
    
    for t in tasks:
        if 'quick' in t['tags'] or 'low_energy' in t['tags']:
            quick_tasks.append(f"• {t['title']}")
        if any(tag == 'wait' or tag.startswith('wait:') for tag in t['tags']):
            waiting_tasks.append(f"• {t['title']} [dim]({' '.join(f'#{tag}' for tag in t['tags'])})[/dim]")

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

    clusters = {}
    for t in tasks:
        pair_tags = [tag.split(':')[1] for tag in t['tags'] if tag.startswith('pair:')]
        for p in pair_tags:
            clusters.setdefault(p, []).append(t['title'])

    cluster_text = ""
    for cluster_name, items in clusters.items():
        cluster_text += f"[bold cyan]Group ({cluster_name}):[/bold cyan]\n"
        for item in items:
            cluster_text += f"  → {item}\n"

    cluster_panel = Panel(
        cluster_text if cluster_text else "[dim]No explicit pairs tagged (#pair:group)[/dim]",
        title="🔗 Natural Task Clusters",
        border_style="blue"
    )

    console.print(timeline_table)
    if future:
        future_text = "\n".join(f"• [{t['time'] or 'Future'}] {t['title']}" for t in future[:3])
        if len(future) > 3:
            future_text += f"\n[dim]...and {len(future) - 3} more[/dim]"
        console.print(Panel(future_text, title=f"📅 Future Tasks ({len(future)} Scheduled)", border_style="cyan"))

    console.print(Columns([quick_panel, waiting_panel]))
    console.print(cluster_panel)

def shift_line_to_tomorrow(raw_line: str) -> str:
    """
    If an explicit date (M/D) exists in the line, increments it by 1 day.
    If no date exists, appends tomorrow's date (M/D) to the task string.
    """
    now = datetime.now()
    today_date = now.date()
    tomorrow_date = today_date + timedelta(days=1)
    
    # Match existing standalone M/D date (e.g., "10/5")
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
            
    # If no date is present, append tomorrow's M/D
    tomorrow_str = f"{tomorrow_date.month}/{tomorrow_date.day}"
    return f"{raw_line.strip()} {tomorrow_str}"

def make_line_today(raw_line: str) -> str:
    """
    Replaces existing explicit M/D date shorthands with today's M/D date,
    or appends today's M/D date if no date exists.
    """
    now = datetime.now()
    today_str = f"{now.month}/{now.day}"
    
    # Match existing standalone M/D date (e.g., "10/12")
    date_match = re.search(r'(?<!\d:)\b(\d{1,2}/\d{1,2})\b(?!\:\d{2})', raw_line)
    
    if date_match:
        # Replace the existing future date with today's date
        return raw_line[:date_match.start(1)] + today_str + raw_line[date_match.end(1):]
        
    # If no date is present, append today's M/D
    return f"{raw_line.strip()} {today_str}"

def toggle_line_focus(file_path: str, raw_line: str) -> None:
    """
    Toggles the #focus tag on raw_line.
    Ensures only one task across the file carries the #focus tag at a time.
    """
    path = Path(file_path)
    if not path.exists():
        return

    lines = path.read_text().splitlines()
    new_lines = []
    target_clean = raw_line.strip()
    is_currently_focused = '#focus' in target_clean

    for line in lines:
        stripped = line.strip()
        # Always clear existing #focus tags from all lines
        cleared_line = re.sub(r'\s*#focus\b', '', line)

        if stripped == target_clean:
            if not is_currently_focused:
                # Add #focus tag to target task
                new_lines.append(f"{cleared_line.rstrip()} #focus")
            else:
                # Task was already focused; leave it cleared (unfocused)
                new_lines.append(cleared_line)
        else:
            new_lines.append(cleared_line)

    path.write_text("\n".join(new_lines) + "\n")
    
if __name__ == "__main__":
    data = parse_tasks("tasks.txt")
    if data["today"] or data["future"]:
        render_dashboard(data)
    else:
        console.print("[yellow]Add tasks to tasks.txt to build your board![/yellow]")