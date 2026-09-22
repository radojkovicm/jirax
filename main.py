"""Entry point for JiraX Time Tracker."""
from database import Database
from gui import TimeTrackerApp


def main():
    db = Database()
    app = TimeTrackerApp(db)
    app.run()


if __name__ == "__main__":
    main()
