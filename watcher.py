import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from board_etl import parse_tasks, render_dashboard

TASK_FILE = "tasks.txt"


class TaskFileHandler(FileSystemEventHandler):
    def __init__(self, target_file):
        self.target_file = Path(target_file).resolve()

    def on_modified(self, event):
        # Trigger re-render whenever tasks.txt is saved/modified
        if Path(event.src_path).resolve() == self.target_file:
            self.refresh_dashboard()

    def refresh_dashboard(self):
        tasks = parse_tasks(str(self.target_file))
        render_dashboard(tasks)


def start_watcher(file_path=TASK_FILE):
    path = Path(file_path)
    if not path.exists():
        path.write_text(
            "! 09:00 - 10:30 Standup & Sprint Sync @work #hard_time\n"
            "* Setup Playwright test runner @work #quick #wait:ci\n"
            "* Convert Page Object helpers @work #focus #pair:playwright\n"
            "? 15:00 Submit weekly timesheet @admin #arbitrary #quick\n"
        )

    event_handler = TaskFileHandler(path)
    
    # Render dashboard immediately on startup
    event_handler.refresh_dashboard()

    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()

    print(f"\n[Watching '{file_path}' for changes... Press Ctrl+C to stop]")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nWatcher stopped.")
    observer.join()


if __name__ == "__main__":
    start_watcher()