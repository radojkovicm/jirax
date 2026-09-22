"""Entry point for JiraX Time Tracker."""
import locale

from database import Database
from gui import TimeTrackerApp


def main():
    try:
        locale.setlocale(locale.LC_ALL, 'sr_RS.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, 'serbian')
        except locale.Error:
            print("Srpska lokalizacija nije dostupna, koristi se podrazumevana")

    db = Database()
    app = TimeTrackerApp(db)
    app.run()


if __name__ == "__main__":
    main()
