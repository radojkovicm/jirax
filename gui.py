"""Tkinter GUI for JiraX Time Tracker."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from tkcalendar import DateEntry
import os

import export


class TimeTrackerApp:
    """Main application window: task entry, reports, stats and future tasks."""

    def __init__(self, db):
        self.db = db
        self.prefilling_from_future_task_id = None

        today = datetime.now().date()
        self.future_date_from_value = today
        self.future_date_to_value = today + timedelta(days=30)

        self.setup_gui()

        self.task_templates = self.load_templates()
        self.recent_tasks = set()
        self.recent_users = set()

        self.total_hours_today = 0
        self.total_hours_week = 0
        self.total_hours_month = 0

    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title("Time Tracker")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)

        try:
            self.root.iconbitmap("time_tracker.ico")
        except tk.TclError:
            print("Icon 'time_tracker.ico' not found or invalid.")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        self.task_frame = ttk.Frame(self.notebook)
        self.report_frame = ttk.Frame(self.notebook)
        self.stats_frame = ttk.Frame(self.notebook)
        self.future_tasks_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.task_frame, text='New Task')
        self.notebook.add(self.report_frame, text='Reports')
        self.notebook.add(self.stats_frame, text='Stats')
        self.notebook.add(self.future_tasks_frame, text="Future Tasks")
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.status_bar = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_text = tk.StringVar()
        self.status_label = ttk.Label(self.status_bar, textvariable=self.status_text, anchor=tk.W, padding=(5, 2))
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.hours_text = tk.StringVar()
        self.hours_label = ttk.Label(self.status_bar, textvariable=self.hours_text, anchor=tk.E, padding=(5, 2))
        self.hours_label.pack(side=tk.RIGHT)

        self.setup_task_entry()
        self.setup_report_tab()
        self.setup_stats_tab()
        self.setup_future_tasks_tab(self.future_tasks_frame)

        self.update_status_bar()

    def on_tab_changed(self, event):
        """Called when the user switches the active tab."""
        try:
            selected_tab_widget = self.notebook.nametowidget(self.notebook.select())
            if selected_tab_widget == self.report_frame:
                self.refresh_report()
            elif selected_tab_widget == self.future_tasks_frame:
                self.refresh_future_tasks()
            elif selected_tab_widget == self.stats_frame:
                self.show_statistics()
            # task_frame usually doesn't need an automatic refresh on selection
        except tk.TclError:
            # This can happen while the notebook is still initializing
            pass
        except Exception as e:
            print(f"Error in on_tab_changed: {e}")

    def update_status_bar(self):
        # Calculate total hours for today, this week and this month
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        cursor = self.db.conn.cursor()
        
        # Hours for today
        cursor.execute("""
            SELECT SUM(hours_spent) FROM tasks 
            WHERE date = ?
        """, (today.strftime('%Y-%m-%d'),))
        today_hours = cursor.fetchone()[0] or 0
        
        # Hours for this week
        cursor.execute("""
            SELECT SUM(hours_spent) FROM tasks 
            WHERE date BETWEEN ? AND ?
        """, (week_start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')))
        week_hours = cursor.fetchone()[0] or 0
        
        # Hours for this month
        cursor.execute("""
            SELECT SUM(hours_spent) FROM tasks 
            WHERE date BETWEEN ? AND ?
        """, (month_start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')))
        month_hours = cursor.fetchone()[0] or 0
        
        self.total_hours_today = today_hours
        self.total_hours_week = week_hours
        self.total_hours_month = month_hours
        
        # Update the status bar
        self.status_text.set(f"Ready | Database: {os.path.abspath('time_tracker.db')}")
        self.hours_text.set(f"Today: {today_hours:.2f}h | Week: {week_hours:.2f}h | Month: {month_hours:.2f}h")

    def get_categories(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM categories ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

    def get_users(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM users ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

    def setup_task_entry(self):
        # Main frame for task entry
        main_frame = ttk.Frame(self.task_frame, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Top section - basic info
        basic_frame = ttk.LabelFrame(main_frame, text="Basic Info", padding=10)
        basic_frame.pack(fill="x", pady=(0, 10))
        
        # Date
        date_frame = ttk.Frame(basic_frame)
        date_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(date_frame, text="Date:").pack(side=tk.LEFT)
        self.date_entry = DateEntry(date_frame, width=12, background='darkblue',
                                  foreground='white', borderwidth=2)
        self.date_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # User
        user_frame = ttk.Frame(basic_frame)
        user_frame.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(user_frame, text="User:").pack(side=tk.LEFT)
        self.user_entry = ttk.Combobox(user_frame, width=20)
        self.user_entry['values'] = self.get_users()
        self.user_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.user_entry.bind('<KeyRelease>', self.update_user_suggestions)
        
        # Priority
        priority_frame = ttk.Frame(basic_frame)
        priority_frame.grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        ttk.Label(priority_frame, text="Priority:").pack(side=tk.LEFT)
        self.priority_combo = ttk.Combobox(priority_frame, width=10)
        self.priority_combo['values'] = ['High', 'Medium', 'Low']
        self.priority_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.priority_combo.set('Medium')
        
        # Task name
        task_frame = ttk.Frame(basic_frame)
        task_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(task_frame, text="Task name:").pack(side=tk.LEFT)
        self.task_entry = ttk.Combobox(task_frame, width=60)
        self.task_entry.pack(side=tk.LEFT, padx=(5, 0), fill="x", expand=True)
        self.task_entry.bind('<KeyRelease>', self.update_task_suggestions)
        
        # Category
        category_frame = ttk.Frame(basic_frame)
        category_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(category_frame, text="Category:").pack(side=tk.LEFT)
        self.category_combo = ttk.Combobox(category_frame, width=30)
        self.category_combo['values'] = self.get_categories()
        self.category_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Grid configuration
        basic_frame.columnconfigure(0, weight=1)
        basic_frame.columnconfigure(1, weight=1)
        basic_frame.columnconfigure(2, weight=1)
        
        # Time frame
        time_frame = ttk.LabelFrame(main_frame, text="Time Tracking", padding=10)
        time_frame.pack(fill="x", pady=(0, 10))
        
        # Start time
        start_frame = ttk.Frame(time_frame)
        start_frame.pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Label(start_frame, text="Start (HH:MM):").pack(side=tk.LEFT)
        self.start_time = tk.StringVar()
        self.start_entry = ttk.Entry(start_frame, textvariable=self.start_time, width=10)
        self.start_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.start_entry.bind('<KeyRelease>', self.calculate_hours)
        self.start_entry.bind('<FocusOut>', self.validate_time_format)

        # End time
        end_frame = ttk.Frame(time_frame)
        end_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(end_frame, text="End (HH:MM):").pack(side=tk.LEFT)
        self.end_time = tk.StringVar()
        self.end_entry = ttk.Entry(end_frame, textvariable=self.end_time, width=10)
        self.end_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.end_entry.bind('<KeyRelease>', self.calculate_hours)
        self.end_entry.bind('<FocusOut>', self.validate_time_format)
        
        # Number of hours
        hours_frame = ttk.Frame(time_frame)
        hours_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(hours_frame, text="Hours:").pack(side=tk.LEFT)
        self.hours_entry = ttk.Entry(hours_frame, width=10)
        self.hours_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Current-time button
        now_button = ttk.Button(time_frame, text="Current Time", 
                              command=self.set_current_time)
        now_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Description
        desc_frame = ttk.LabelFrame(main_frame, text="Task Description", padding=10)
        desc_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.desc_text = tk.Text(desc_frame, height=5, width=40)
        self.desc_text.pack(fill="both", expand=True)

        # Future task checkbox
        checkbox_frame = ttk.Frame(main_frame)
        checkbox_frame.pack(fill="x", pady=(0, 5))

        # Future task checkbox
        self.future_task_var = tk.BooleanVar()
        self.future_task_check = ttk.Checkbutton(checkbox_frame, text="Future task",
                                                variable=self.future_task_var)
        self.future_task_check.pack(side=tk.LEFT, padx=5)

        # Checkbox for marking a task as completed (future tasks only)
        self.completed_var = tk.BooleanVar()
        self.completed_check = ttk.Checkbutton(checkbox_frame, text="Completed",
                                            variable=self.completed_var)
        self.completed_check.pack(side=tk.LEFT, padx=5)
        self.completed_check.grid_remove()  # Hidden by default

        # Wire the checkbox state change to the handler
        self.future_task_var.trace_add("write", lambda *args: self.toggle_completed_checkbox())
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Button(button_frame, text="Save Task", 
                 command=self.save_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Save as Template", 
                 command=self.save_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Load Template", 
                 command=self.load_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Copy Last Task", 
                 command=self.copy_last_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Fields", 
                 command=self.clear_fields).pack(side=tk.RIGHT, padx=5)


    def setup_report_tab(self):
        # Main frame for reports
        main_report_frame = ttk.Frame(self.report_frame, padding=10)
        main_report_frame.pack(fill="both", expand=True)

        # Filter frame
        filter_frame = ttk.LabelFrame(main_report_frame, text="Filters", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))

        # Start date
        from_frame = ttk.Frame(filter_frame)
        from_frame.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(from_frame, text="From:").pack(side=tk.LEFT)
        self.date_from = DateEntry(from_frame, width=12, background='darkblue',
                                foreground='white', borderwidth=2, date_pattern='dd.MM.yyyy')
        self.date_from.pack(side=tk.LEFT, padx=(5,0))

        # End date
        to_frame = ttk.Frame(filter_frame)
        to_frame.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(to_frame, text="To:").pack(side=tk.LEFT)
        self.date_to = DateEntry(to_frame, width=12, background='darkblue',
                                foreground='white', borderwidth=2, date_pattern='dd.MM.yyyy')
        self.date_to.pack(side=tk.LEFT, padx=(5,0))

        # Category filter
        category_filter_frame = ttk.Frame(filter_frame)
        category_filter_frame.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Label(category_filter_frame, text="Category:").pack(side=tk.LEFT)
        self.filter_category = ttk.Combobox(category_filter_frame, width=15)
        self.filter_category['values'] = ['All'] + self.get_categories()
        self.filter_category.current(0)
        self.filter_category.pack(side=tk.LEFT, padx=(5,0))

        # User filter
        user_filter_frame = ttk.Frame(filter_frame)
        user_filter_frame.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(user_filter_frame, text="User:").pack(side=tk.LEFT)
        self.filter_user = ttk.Combobox(user_filter_frame, width=15)
        self.filter_user['values'] = ['All'] + self.get_users()
        self.filter_user.current(0)
        self.filter_user.pack(side=tk.LEFT, padx=(5,0))

        # Refresh and export buttons
        buttons_frame = ttk.Frame(filter_frame)
        buttons_frame.grid(row=0, column=4, padx=5, pady=5, sticky="e")
        ttk.Button(buttons_frame, text="Refresh", command=self.refresh_report).pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(buttons_frame, text="Export to Excel", command=self.export_to_excel).pack(side=tk.LEFT)

        filter_frame.columnconfigure(4, weight=1) # Push the buttons to the right

        # Treeview frame
        tree_view_frame = ttk.Frame(main_report_frame)
        tree_view_frame.pack(fill="both", expand=True, pady=(10,0))

        # Create the Treeview
        self.tree = ttk.Treeview(tree_view_frame, columns=("#", "Date", "User", "Task", "Category",
                                                        "Hours", "Start", "End", "Priority", "Actions"),
                                show="headings")
        self.tree.heading("#", text="#")
        self.tree.heading("Date", text="Date")
        self.tree.heading("User", text="User")
        self.tree.heading("Task", text="Task")
        self.tree.heading("Category", text="Category")
        self.tree.heading("Hours", text="Hours")
        self.tree.heading("Start", text="Start")
        self.tree.heading("End", text="End")
        self.tree.heading("Priority", text="Priority")
        self.tree.heading("Actions", text="Actions")

        self.tree.column("#", width=30, anchor="center")
        self.tree.column("Date", width=100, anchor="center")
        self.tree.column("User", width=120)
        self.tree.column("Task", width=250)
        self.tree.column("Category", width=120)
        self.tree.column("Hours", width=60, anchor="e")
        self.tree.column("Start", width=70, anchor="center")
        self.tree.column("End", width=70, anchor="center")
        self.tree.column("Priority", width=80, anchor="center")
        self.tree.column("Actions", width=100, anchor="center")


        # Add scrollbars
        vsb = ttk.Scrollbar(tree_view_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_view_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_view_frame.grid_columnconfigure(0, weight=1)
        tree_view_frame.grid_rowconfigure(0, weight=1)

        # Wire up events
        self.tree.bind("<Double-1>", self.show_task_details)
        self.tree.bind("<Button-3>", self.show_edit_menu)

        # Row styles
        self.tree.tag_configure('oddrow', background='#f0f0f0')
        self.tree.tag_configure('evenrow', background='white')
        self.tree.tag_configure('total', background='#e0e0e0', font=('TkDefaultFont', 10, 'bold'))
        self.tree.tag_configure('separator', background='gray')

    def setup_stats_tab(self):
        # Main frame for statistics
        main_frame = ttk.Frame(self.stats_frame, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Filter frame
        filter_frame = ttk.LabelFrame(main_frame, text="Period", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))
        
        # Start date
        from_frame = ttk.Frame(filter_frame)
        from_frame.grid(row=0, column=0, padx=5, pady=5)
        
        ttk.Label(from_frame, text="From:").pack(side=tk.LEFT)
        self.stats_date_from = DateEntry(from_frame, width=12)
        self.stats_date_from.set_date(datetime.now().date().replace(day=1))  # First day of the month
        self.stats_date_from.pack(side=tk.LEFT, padx=(5, 0))
        
        # End date
        to_frame = ttk.Frame(filter_frame)
        to_frame.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(to_frame, text="To:").pack(side=tk.LEFT)
        self.stats_date_to = DateEntry(to_frame, width=12)
        self.stats_date_to.pack(side=tk.LEFT, padx=(5, 0))
        
        # Buttons
        button_frame = ttk.Frame(filter_frame)
        button_frame.grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Button(button_frame, text="Show Statistics", 
                 command=self.show_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Statistics", 
                 command=self.export_statistics).pack(side=tk.LEFT, padx=5)
        
        # Grid configuration
        filter_frame.columnconfigure(0, weight=1)
        filter_frame.columnconfigure(1, weight=1)
        filter_frame.columnconfigure(2, weight=2)
        
        # Statistics display frame
        stats_display_frame = ttk.Frame(main_frame)
        stats_display_frame.pack(fill="both", expand=True)
        
        # Left panel - stats by category
        cat_frame = ttk.LabelFrame(stats_display_frame, text="By Category", padding=10)
        cat_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=(0, 5))
        
        self.cat_tree = ttk.Treeview(cat_frame, columns=("Category", "Hours", "Percentage"),
                                   show="headings")
        self.cat_tree.heading("Category", text="Category")
        self.cat_tree.heading("Hours", text="Hours")
        self.cat_tree.heading("Percentage", text="%")
        
        self.cat_tree.column("Category", width=150)
        self.cat_tree.column("Hours", width=70, anchor="center")
        self.cat_tree.column("Percentage", width=70, anchor="center")
        
        self.cat_tree.pack(fill="both", expand=True)
        
        # Right panel - stats by user
        user_frame = ttk.LabelFrame(stats_display_frame, text="By User", padding=10)
        user_frame.pack(side=tk.RIGHT, fill="both", expand=True, padx=(5, 0))
        
        self.user_tree = ttk.Treeview(user_frame, columns=("User", "Hours", "Percentage"),
                                    show="headings")
        self.user_tree.heading("User", text="User")
        self.user_tree.heading("Hours", text="Hours")
        self.user_tree.heading("Percentage", text="%")
        
        self.user_tree.column("User", width=150)
        self.user_tree.column("Hours", width=70, anchor="center")
        self.user_tree.column("Percentage", width=70, anchor="center")
        
        self.user_tree.pack(fill="both", expand=True)
        

    def setup_future_tasks_tab(self, parent_frame):
        # Main frame for future tasks inside parent_frame
        main_future_frame = ttk.Frame(parent_frame, padding=10)
        main_future_frame.pack(fill="both", expand=True)

        # Filter frame
        filter_frame = ttk.LabelFrame(main_future_frame, text="Future Task Filters", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))

        # Start date
        future_from_frame = ttk.Frame(filter_frame)
        future_from_frame.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(future_from_frame, text="From:").pack(side=tk.LEFT)
        self.future_date_from = DateEntry(future_from_frame, width=12, background='darkblue',
                                        foreground='white', borderwidth=2, date_pattern='dd.MM.yyyy')
        self.future_date_from.set_date(self.future_date_from_value) # Uses the value from __init__
        self.future_date_from.pack(side=tk.LEFT, padx=(5, 0))

        # End date
        future_to_frame = ttk.Frame(filter_frame)
        future_to_frame.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(future_to_frame, text="To:").pack(side=tk.LEFT)
        self.future_date_to = DateEntry(future_to_frame, width=12, background='darkblue',
                                        foreground='white', borderwidth=2, date_pattern='dd.MM.yyyy')
        self.future_date_to.set_date(self.future_date_to_value) # Uses the value from __init__
        self.future_date_to.pack(side=tk.LEFT, padx=(5, 0))

        # User filter
        future_user_filter_frame = ttk.Frame(filter_frame)
        future_user_filter_frame.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Label(future_user_filter_frame, text="User:").pack(side=tk.LEFT)
        self.future_user_filter = ttk.Combobox(future_user_filter_frame, width=15)
        self.future_user_filter['values'] = ['All'] + self.get_all_users()
        self.future_user_filter.current(0)
        self.future_user_filter.pack(side=tk.LEFT, padx=(5, 0))

        # Category filter
        future_category_filter_frame = ttk.Frame(filter_frame)
        future_category_filter_frame.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(future_category_filter_frame, text="Category:").pack(side=tk.LEFT)
        self.future_category_filter = ttk.Combobox(future_category_filter_frame, width=15)
        self.future_category_filter['values'] = ['All'] + self.get_all_categories()
        self.future_category_filter.current(0)
        self.future_category_filter.pack(side=tk.LEFT, padx=(5, 0))

        # Refresh button
        refresh_button_frame = ttk.Frame(filter_frame)
        refresh_button_frame.grid(row=0, column=4, padx=5, pady=5, sticky="e")
        ttk.Button(refresh_button_frame, text="Refresh", command=self.refresh_future_tasks).pack(side=tk.LEFT)

        filter_frame.columnconfigure(4, weight=1) # Push the button to the right if there's room

        # Treeview frame
        tree_view_frame = ttk.Frame(main_future_frame)
        tree_view_frame.pack(fill="both", expand=True, pady=(10,0))

        # Create the future tasks Treeview
        self.future_tree = ttk.Treeview(tree_view_frame, columns=("#", "Date", "User", "Task", "Category", "Priority", "Status"),
                                    show="headings")
        self.future_tree.heading("#", text="#")
        self.future_tree.heading("Date", text="Date")
        self.future_tree.heading("User", text="User")
        self.future_tree.heading("Task", text="Task")
        self.future_tree.heading("Category", text="Category")
        self.future_tree.heading("Priority", text="Priority")
        self.future_tree.heading("Status", text="Status")

        self.future_tree.column("#", width=30, anchor="center")
        self.future_tree.column("Date", width=100, anchor="center")
        self.future_tree.column("User", width=120)
        self.future_tree.column("Task", width=250)
        self.future_tree.column("Category", width=120)
        self.future_tree.column("Priority", width=80, anchor="center")
        self.future_tree.column("Status", width=100, anchor="center")

        # Add scrollbars
        vsb_future = ttk.Scrollbar(tree_view_frame, orient="vertical", command=self.future_tree.yview)
        hsb_future = ttk.Scrollbar(tree_view_frame, orient="horizontal", command=self.future_tree.xview)
        self.future_tree.configure(yscrollcommand=vsb_future.set, xscrollcommand=hsb_future.set)

        self.future_tree.grid(row=0, column=0, sticky="nsew")
        vsb_future.grid(row=0, column=1, sticky="ns")
        hsb_future.grid(row=1, column=0, sticky="ew")

        tree_view_frame.grid_columnconfigure(0, weight=1)
        tree_view_frame.grid_rowconfigure(0, weight=1)


        # Wire up events
        self.future_tree.bind("<Double-1>", self.show_future_task_details)
        self.future_tree.bind("<Button-3>", self.show_future_task_context_menu) # context menu binding

        # Row styles (optional alternating colors)
        self.future_tree.tag_configure('oddrow', background='#f0f0f0')
        self.future_tree.tag_configure('evenrow', background='white')

    def update_user_suggestions(self, event=None):
        if event and event.keysym in ('Down', 'Up', 'Return', 'Tab'):
            return

        current_text = self.user_entry.get().lower()
        
        if not current_text:
            self.user_entry['values'] = self.get_users()
            return
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT name FROM users 
            WHERE LOWER(name) LIKE ? 
            ORDER BY name
        """, (f"%{current_text}%",))
        
        suggestions = [row[0] for row in cursor.fetchall()]
        
        if suggestions:
            self.user_entry['values'] = suggestions
            
            if len(suggestions) == 1 and suggestions[0].lower() == current_text:
                self.user_entry.selection_clear()
            else:
                if not self.user_entry.winfo_ismapped():
                    self.user_entry.event_generate('<Down>')

    def update_task_suggestions(self, event=None):
        if event and event.keysym in ('Down', 'Up', 'Return', 'Tab'):
            return

        current_text = self.task_entry.get().lower()
        
        if not current_text:
            return
        
        cursor = self.db.conn.cursor()
        
        # Get suggestions from tasks
        cursor.execute("""
            SELECT DISTINCT task_name 
            FROM tasks 
            WHERE LOWER(task_name) LIKE ? 
            ORDER BY id DESC LIMIT 10
        """, (f"%{current_text}%",))
        
        db_suggestions = [row[0] for row in cursor.fetchall()]
        
        # Get suggestions from templates
        cursor.execute("""
            SELECT DISTINCT task_name 
            FROM templates 
            WHERE LOWER(task_name) LIKE ? 
            ORDER BY id DESC LIMIT 5
        """, (f"%{current_text}%",))
        
        template_suggestions = [row[0] for row in cursor.fetchall()]
        
        # Combine and de-duplicate
        all_suggestions = list(dict.fromkeys(db_suggestions + template_suggestions))[:10]
        
        if all_suggestions:
            self.task_entry['values'] = all_suggestions
            
            if len(all_suggestions) == 1 and all_suggestions[0].lower() == current_text:
                self.task_entry.selection_clear()
            else:
                if not self.task_entry.winfo_ismapped():
                    self.task_entry.event_generate('<Down>')

    def validate_time_format(self, event=None):
        """Validate the time format (HH:MM)"""
        widget = event.widget
        time_str = widget.get()
        
        if not time_str:
            return
        
        try:
            # Check the format
            if len(time_str) != 5 or time_str[2] != ':':
                raise ValueError("Invalid format")
            
            hours, minutes = map(int, time_str.split(':'))
            
            if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                raise ValueError("Invalid time")
                
        except ValueError:
            messagebox.showerror("Error", "Invalid time format. Use HH:MM (e.g. 09:30)")
            widget.delete(0, tk.END)
            widget.focus_set()

    def calculate_hours(self, event=None):
        """Calculate the number of hours between the start and end time"""
        try:
            start = self.start_time.get()
            end = self.end_time.get()
            
            if start and end and len(start) == 5 and len(end) == 5:
                start_dt = datetime.strptime(start, '%H:%M')
                end_dt = datetime.strptime(end, '%H:%M')
                
                # If the end time is before the start time, assume it's the next day
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                    
                diff = end_dt - start_dt
                hours = diff.total_seconds() / 3600
                
                self.hours_entry.delete(0, tk.END)
                self.hours_entry.insert(0, f"{hours:.2f}")
        except ValueError:
            pass


    def set_current_time(self):
        """Sets the start time to the end of the last task for the given day, or 08:00."""
        selected_date_str = self.date_entry.get_date().strftime('%Y-%m-%d')
        # selected_user_name = self.user_entry.get()

        cursor = self.db.conn.cursor()

        # Find the last end_time for the selected date
        # You can add user_id to the WHERE clause to scope this to a specific user
        # JOIN users u ON tasks.user_id = u.id AND u.name = ?
        # params.append(selected_user_name)
        query = """
            SELECT end_time FROM tasks
            WHERE date = ? AND end_time IS NOT NULL AND end_time != ''
            ORDER BY end_time DESC
            LIMIT 1
        """
        params = [selected_date_str]

        cursor.execute(query, params)
        last_task_end_time = cursor.fetchone()

        next_start_time_str = "08:00" # Default time

        if last_task_end_time and last_task_end_time[0]:
            # Check the HH:MM format
            try:
                datetime.strptime(last_task_end_time[0], '%H:%M')
                next_start_time_str = last_task_end_time[0]
            except ValueError:
                # If the format is invalid, use the default
                print(f"Warning: Invalid end_time format '{last_task_end_time[0]}' in the database, using 08:00.")
                pass # next_start_time_str stays "08:00"

        self.start_time.set(next_start_time_str)
        self.end_time.set("")  # Clear the end time
        self.hours_entry.delete(0, tk.END) # Clear the hours
        self.start_entry.focus_set() # Focus the start time entry
        # No need to call calculate_hours() here since end_time is empty

    def clear_fields(self):
        """Clear all entry fields"""
        self.task_entry.set('')
        self.desc_text.delete("1.0", tk.END)
        self.hours_entry.delete(0, tk.END)
        self.start_time.set('')
        self.end_time.set('')
        self.priority_combo.set('Medium')
        # Don't clear date and user since they're often the same value
        

    def toggle_completed_checkbox(self):
        if self.future_task_var.get():
            self.completed_check.pack()  # Show the completed checkbox
            # Hide the time fields
            self.hours_entry.config(state=tk.DISABLED)
            self.start_entry.config(state=tk.DISABLED)
            self.end_entry.config(state=tk.DISABLED)
        else:
            self.completed_check.pack_forget()  # Hide the completed checkbox
            # Show the time fields
            self.hours_entry.config(state=tk.NORMAL)
            self.start_entry.config(state=tk.NORMAL)
            self.end_entry.config(state=tk.NORMAL)


    def prepare_future_task_for_entry(self, future_task_id_str):
        """Prepares a future task for entry in the 'New Task' tab."""
        try:
            future_task_id = int(future_task_id_str)
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT ft.date, u.name as user_name, ft.task_name, c.name as category_name,
                    ft.description, ft.priority
                FROM future_tasks ft
                LEFT JOIN users u ON ft.user_id = u.id
                LEFT JOIN categories c ON ft.category_id = c.id
                WHERE ft.id = ?
            """, (future_task_id,))
            task_data = cursor.fetchone()

            if not task_data:
                messagebox.showerror("Error", "Future task not found.")
                return

            # Unpack the data
            task_date_str, user_name, task_name, category_name, description, priority = task_data

            # Fill in the fields in the 'New Task' tab
            self.date_entry.set_date(datetime.now().date())

            self.user_entry.set(user_name if user_name else "")
            self.task_entry.set(task_name if task_name else "") # self.task_entry is the entry widget
            self.category_combo.set(category_name if category_name else "")
            self.desc_text.delete("1.0", tk.END)
            self.desc_text.insert("1.0", description if description else "")
            self.priority_combo.set(priority if priority else "Medium")

            self.start_time.set("")
            self.end_time.set("")
            self.hours_entry.delete(0, tk.END)

            self.future_task_var.set(False)
            self.completed_var.set(False)

            self.prefilling_from_future_task_id = future_task_id

            self.notebook.select(self.task_frame)
            # focus the task entry widget:
            # Assumes the task-name entry widget is called self.task_entry
            if hasattr(self, 'task_entry') and self.task_entry:
                self.task_entry.focus_set()
            # If it was named differently (e.g. self.task_name_entry), use that name:
            # elif hasattr(self, 'task_name_entry') and self.task_name_entry:
            #     self.task_name_entry.focus_set()
            else:
                print("Warning: Task name entry widget (task_entry) not found to set focus.")


            messagebox.showinfo("Information", "Future task details have been filled in. Enter the time and save as an active task.")

        except ValueError:
            messagebox.showerror("Error", "Invalid future task ID.")
        except Exception as e:
            messagebox.showerror("Error", f"Error preparing task for entry: {str(e)}")
            print(f"Error preparing future task for entry: {str(e)}")
        

    def save_task(self):
        """Save a new task to the database"""
        try:
            # ... (gather form data and validate) ...
            date_str = self.date_entry.get_date().strftime('%Y-%m-%d')
            user = self.user_entry.get()
            task_name = self.task_entry.get()
            category = self.category_combo.get()
            description = self.desc_text.get("1.0", tk.END).strip()
            priority_val = self.priority_combo.get()
            is_future_task_checkbox = self.future_task_var.get() # Renamed to avoid clashing with the is_future_task logic
            hours = 0.0
            start_time_str = ""
            end_time_str = ""

            if not all([task_name, category, user]):
                messagebox.showerror("Error", "Please fill in all required fields (user, task, category)")
                return

            if not is_future_task_checkbox: # If the "Future task" checkbox is NOT checked
                # Validate hours and collect times for REGULAR tasks only
                # ... (hours/time validation logic) ...
                if not self.hours_entry.get() and (not self.start_time.get() or not self.end_time.get()):
                    messagebox.showerror("Error", "For an active task, enter the number of hours or a start/end time.")
                    return
                try:
                    if self.hours_entry.get():
                        hours = float(self.hours_entry.get())
                        if hours <= 0:
                            raise ValueError("Hours must be a positive number")
                    elif self.start_time.get() and self.end_time.get():
                        self.calculate_hours()
                        if self.hours_entry.get():
                            hours = float(self.hours_entry.get())
                            if hours <= 0:
                                if not (datetime.strptime(self.end_time.get(), '%H:%M') < datetime.strptime(self.start_time.get(), '%H:%M')):
                                    messagebox.showerror("Error", "Invalid hours entry. Check the start/end time or enter hours directly.")
                                    return
                        else:
                            messagebox.showerror("Error", "Enter a valid number of hours or a start/end time.")
                            return
                    else:
                        messagebox.showerror("Error", "Enter the number of hours or a start/end time for the active task.")
                        return
                except ValueError:
                    messagebox.showerror("Error", "Enter a valid number of hours.")
                    return
                start_time_str = self.start_time.get()
                end_time_str = self.end_time.get()
            # else: Future tasks don't need hours or time

            cursor = self.db.conn.cursor()
            # ... (get/create category_id and user_id) ...
            # Look up the category, creating it if it doesn't exist
            if category:
                cursor.execute("SELECT id FROM categories WHERE name = ?", (category,))
                category_result = cursor.fetchone()
                if not category_result:
                    cursor.execute("INSERT INTO categories (name) VALUES (?)", (category,))
                    self.db.conn.commit()
                    category_id = cursor.lastrowid
                else:
                    category_id = category_result[0]
            else:
                messagebox.showerror("Error", "Please enter a category")
                return

            # Look up the user, creating it if it doesn't exist
            if user:
                cursor.execute("SELECT id FROM users WHERE name = ?", (user,))
                user_result = cursor.fetchone()
                if not user_result:
                    cursor.execute("INSERT INTO users (name) VALUES (?)", (user,))
                    self.db.conn.commit()
                    user_id = cursor.lastrowid
                else:
                    user_id = user_result[0]
            else:
                messagebox.showerror("Error", "Please enter a user")
                return


            if is_future_task_checkbox: # If the "Future task" checkbox is checked
                # Save a NEW future task
                cursor.execute("""
                    INSERT INTO future_tasks (date, user_id, category_id, task_name, description, priority, completed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str, user_id, category_id, task_name, description, priority_val,
                    1 if self.completed_var.get() else 0
                ))
                self.db.conn.commit()
                messagebox.showinfo("Success", "Future task saved successfully!")
                self.refresh_future_tasks()
            else: # If the "Future task" checkbox is NOT checked -> save as an ACTIVE task
                cursor.execute("""
                    INSERT INTO tasks (date, user_id, category_id, task_name, description,
                                    hours_spent, start_time, end_time, priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str, user_id, category_id, task_name, description,
                    hours, start_time_str, end_time_str, priority_val
                ))
                self.db.conn.commit()
                messagebox.showinfo("Success", "Active task saved successfully!")

                # If this active task came from moving a future task,
                # delete the original future task
                if self.prefilling_from_future_task_id is not None:
                    try:
                        cursor.execute("DELETE FROM future_tasks WHERE id = ?", (self.prefilling_from_future_task_id,))
                        self.db.conn.commit()
                        print(f"Debug: deleted future task with ID: {self.prefilling_from_future_task_id}")
                        self.prefilling_from_future_task_id = None # Reset the ID
                        self.refresh_future_tasks() # Refresh the future tasks list
                    except Exception as e_del:
                        print(f"Error deleting the original future task: {e_del}")
                        messagebox.showwarning("Warning", f"The task was saved as active, but an error occurred while deleting the original future task: {e_del}")


            # Update recent tasks and users
            self.recent_tasks.add(task_name)
            self.recent_users.add(user)

            # Update the report and status bar
            self.refresh_report()
            self.update_status_bar()
            self._update_filter_comboboxes()

            # Clear the fields
            self.task_entry.set('')
            self.desc_text.delete("1.0", tk.END)
            self.hours_entry.delete(0, tk.END)
            self.start_time.set('')
            self.end_time.set('')
            # Don't clear user/category immediately - the user may want to enter more tasks for the same one
            self.category_combo.set('')
            self.user_entry.set('')
            self.priority_combo.set('Medium')
            self.future_task_var.set(False)
            self.completed_var.set(False)

            # If this wasn't a move from a future task, reset the ID just in case
            # (though it should already be None if there was no move)
            if not is_future_task_checkbox and self.prefilling_from_future_task_id is not None:
                # This happens if the user clicked "Move", then checked "Future task" and saved.
                # In that case the original shouldn't be deleted. Only reset if saved as ACTIVE.
                pass # Already handled above
            elif self.prefilling_from_future_task_id is not None and is_future_task_checkbox:
                # The user moved it, but then decided to save it as a NEW future task instead.
                # In that case, leave the original alone and just reset the flag.
                self.prefilling_from_future_task_id = None


        except Exception as e:
            messagebox.showerror("Error", f"Error saving task: {str(e)}")
            print(f"Error saving task: {str(e)}")
            # If an error occurred while prefilling_from_future_task_id was set,
            # it may be best not to reset it so the user can retry without moving the task again.
            # Or reset it to avoid unexpected behavior on the next save.
            # For now, leave it untouched here in the except block.

    def _update_filter_comboboxes(self):
        """Refreshes the values in all category/user filter comboboxes."""
        all_categories = self.get_categories()
        all_users = self.get_users()

        # Save the currently selected values so they can be restored
        current_filter_cat = self.filter_category.get()
        current_filter_user = self.filter_user.get()
        current_future_cat = self.future_category_filter.get()
        current_future_user = self.future_user_filter.get()
        current_task_cat = self.category_combo.get() # For task entry
        current_task_user = self.user_entry.get() # For task entry


        # Report tab filters
        self.filter_category['values'] = ['All'] + all_categories
        if current_filter_cat in self.filter_category['values']:
            self.filter_category.set(current_filter_cat)
        elif self.filter_category['values']:
            self.filter_category.current(0) # Fall back to "All" if the previous value no longer exists

        self.filter_user['values'] = ['All'] + all_users
        if current_filter_user in self.filter_user['values']:
            self.filter_user.set(current_filter_user)
        elif self.filter_user['values']:
            self.filter_user.current(0) # Fall back to "All"

        # Future tasks tab filters
        # get_all_categories/get_all_users are the same as get_categories/get_users
        self.future_category_filter['values'] = ['All'] + all_categories
        if current_future_cat in self.future_category_filter['values']:
            self.future_category_filter.set(current_future_cat)
        elif self.future_category_filter['values']:
            self.future_category_filter.current(0)

        self.future_user_filter['values'] = ['All'] + all_users
        if current_future_user in self.future_user_filter['values']:
            self.future_user_filter.set(current_future_user)
        elif self.future_user_filter['values']:
            self.future_user_filter.current(0)

        # Task entry tab (in case new categories/users are added directly)
        self.category_combo['values'] = all_categories
        if current_task_cat in self.category_combo['values']:
            self.category_combo.set(current_task_cat)
        # else: self.category_combo.set('') # Or leave it empty

        self.user_entry['values'] = all_users
        if current_task_user in self.user_entry['values']:
            self.user_entry.set(current_task_user)
        else: self.user_entry.set('') # Or leave it empty
    

    def load_templates(self):
        """Load all templates from the database"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT templates.task_name, users.name, categories.name, templates.description 
            FROM templates 
            JOIN categories ON templates.category_id = categories.id
            LEFT JOIN users ON templates.user_id = users.id
        """)
        return cursor.fetchall()

    def save_template(self):
        """Save the current task as a template"""
        task_name = self.task_entry.get()
        user = self.user_entry.get()
        category = self.category_combo.get()
        description = self.desc_text.get("1.0", tk.END).strip()

        if not task_name or not category:
            messagebox.showerror("Error", "Please fill in the task name and category")
            return

        try:
            cursor = self.db.conn.cursor()
            
            # Get the category ID
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category,))
            category_result = cursor.fetchone()
            if not category_result:
                messagebox.showerror("Error", f"Category '{category}' does not exist")
                return
            category_id = category_result[0]
            
            # Get the user ID
            user_id = None
            if user:
                cursor.execute("SELECT id FROM users WHERE name = ?", (user,))
                user_result = cursor.fetchone()
                if not user_result:
                    # If the user doesn't exist, add them
                    cursor.execute("INSERT INTO users (name) VALUES (?)", (user,))
                    self.db.conn.commit()
                    user_id = cursor.lastrowid
                else:
                    user_id = user_result[0]

            # Check whether the template already exists
            cursor.execute("""
                SELECT id FROM templates 
                WHERE task_name = ? AND category_id = ? AND 
                      (user_id = ? OR (user_id IS NULL AND ? IS NULL))
            """, (task_name, category_id, user_id, user_id))
            
            existing = cursor.fetchone()
            if existing:
                if messagebox.askyesno("Warning", "A template with the same name already exists. Replace it?"):
                    cursor.execute("""
                        UPDATE templates 
                        SET description = ?, user_id = ?
                        WHERE id = ?
                    """, (description, user_id, existing[0]))
                else:
                    return
            else:
                cursor.execute("""
                    INSERT INTO templates (task_name, user_id, category_id, description)
                    VALUES (?, ?, ?, ?)
                """, (task_name, user_id, category_id, description))

            self.db.conn.commit()
            self.task_templates = self.load_templates()
            self._update_filter_comboboxes()
            messagebox.showinfo("Success", "Template saved successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Error saving template: {str(e)}")
            # Log the error
            print(f"Error saving template: {str(e)}")

    def load_template(self):
        """Load a template from the database"""
        if not self.task_templates:
            messagebox.showinfo("Info", "No templates available")
            return

        template_window = tk.Toplevel(self.root)
        template_window.title("Load Template")
        template_window.geometry("500x400")
        template_window.transient(self.root)
        template_window.grab_set()

        # Search frame
        search_frame = ttk.Frame(template_window, padding=5)
        search_frame.pack(fill="x")
        
        ttk.Label(search_frame, text="Search:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
        
        # Template list
        template_frame = ttk.Frame(template_window)
        template_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        template_list = ttk.Treeview(template_frame, columns=("Task", "User", "Category"), 
                                   show="headings", height=15)
        template_list.heading("Task", text="Task name")
        template_list.heading("User", text="User")
        template_list.heading("Category", text="Category")
        
        template_list.column("Task", width=200)
        template_list.column("User", width=100)
        template_list.column("Category", width=150)
        
        vsb = ttk.Scrollbar(template_frame, orient="vertical", command=template_list.yview)
        template_list.configure(yscrollcommand=vsb.set)
        
        template_list.pack(side=tk.LEFT, fill="both", expand=True)
        vsb.pack(side=tk.RIGHT, fill="y")
        
        # Template description
        desc_frame = ttk.LabelFrame(template_window, text="Description", padding=5)
        desc_frame.pack(fill="x", padx=5, pady=5)
        
        desc_text = tk.Text(desc_frame, height=5, width=40, wrap=tk.WORD)
        desc_text.pack(fill="both", expand=True)
        desc_text.config(state=tk.DISABLED)
        
        # Buttons
        button_frame = ttk.Frame(template_window, padding=5)
        button_frame.pack(fill="x")
        
        ttk.Button(button_frame, text="Apply", 
                 command=lambda: apply_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Template", 
                 command=lambda: delete_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", 
                 command=template_window.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Populate the template list
        def populate_templates(search_text=""):
            template_list.delete(*template_list.get_children())
            search_text = search_text.lower()
            
            for template in self.task_templates:
                task_name, user_name, category_name, description = template
                
                if (search_text in task_name.lower() or 
                    (user_name and search_text in user_name.lower()) or 
                    search_text in category_name.lower()):
                    template_list.insert("", tk.END, values=(task_name, user_name or "", category_name))
        
        # Show the template description
        def show_description(event):
            selection = template_list.selection()
            if not selection:
                return
            
            selected = template_list.item(selection[0])['values']
            task_name, user_name, category_name = selected
            
            for template in self.task_templates:
                if (template[0] == task_name and 
                    (template[1] or "") == user_name and 
                    template[2] == category_name):
                    desc_text.config(state=tk.NORMAL)
                    desc_text.delete("1.0", tk.END)
                    desc_text.insert("1.0", template[3] or "")
                    desc_text.config(state=tk.DISABLED)
                    break
        
        # Apply the template
        def apply_template():
            selection = template_list.selection()
            if not selection:
                messagebox.showinfo("Info", "Please select a template")
                return
            
            selected = template_list.item(selection[0])['values']
            task_name, user_name, category_name = selected
            
            self.task_entry.set(task_name)
            if user_name:
                self.user_entry.set(user_name)
            self.category_combo.set(category_name)
            
            for template in self.task_templates:
                if (template[0] == task_name and 
                    (template[1] or "") == user_name and 
                    template[2] == category_name):
                    self.desc_text.delete("1.0", tk.END)
                    self.desc_text.insert("1.0", template[3] or "")
                    break
            
            template_window.destroy()
        
        # Delete the template
        def delete_template():
            selection = template_list.selection()
            if not selection:
                messagebox.showinfo("Info", "Please select a template")
                return
            
            if not messagebox.askyesno("Confirm", "Are you sure you want to delete this template?"):
                return
            
            selected = template_list.item(selection[0])['values']
            task_name, user_name, category_name = selected
            
            try:
                cursor = self.db.conn.cursor()
                
                # Get the category ID
                cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
                category_id = cursor.fetchone()[0]
                
                # Get the user ID
                user_id = None
                if user_name:
                    cursor.execute("SELECT id FROM users WHERE name = ?", (user_name,))
                    user_result = cursor.fetchone()
                    if user_result:
                        user_id = user_result[0]
                
                # Delete the template
                cursor.execute("""
                    DELETE FROM templates 
                    WHERE task_name = ? AND category_id = ? AND 
                          (user_id = ? OR (user_id IS NULL AND ? IS NULL))
                """, (task_name, category_id, user_id, user_id))
                
                self.db.conn.commit()
                self.task_templates = self.load_templates()
                
                populate_templates(search_var.get())
                messagebox.showinfo("Success", "Template deleted successfully!")
                
            except Exception as e:
                messagebox.showerror("Error", f"Error deleting template: {str(e)}")
        
        # Search templates
        def search_templates(*args):
            populate_templates(search_var.get())
        
        search_var.trace("w", search_templates)
        template_list.bind('<Double-1>', lambda e: apply_template())
        template_list.bind('<<TreeviewSelect>>', show_description)
        
        # Initial population
        populate_templates()
        
        # Focus the search field
        search_entry.focus_set()

    def copy_last_task(self):
        """Copy the last entered task"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT tasks.task_name, users.name, categories.name, tasks.description, 
                   tasks.start_time, tasks.end_time, tasks.priority
            FROM tasks 
            JOIN categories ON tasks.category_id = categories.id 
            LEFT JOIN users ON tasks.user_id = users.id
            ORDER BY tasks.id DESC LIMIT 1
        """)
        last_task = cursor.fetchone()

        if last_task:
            self.task_entry.set(last_task[0])
            if last_task[1]:
                self.user_entry.set(last_task[1])
            self.category_combo.set(last_task[2])
            self.desc_text.delete("1.0", tk.END)
            self.desc_text.insert("1.0", last_task[3] or "")
            self.start_time.set(last_task[4] or "")
            self.end_time.set(last_task[5] or "")
            self.priority_combo.set(last_task[6] or "")
        else:
            messagebox.showinfo("Info", "No previous tasks")

    def refresh_report(self):
        """Refresh the report based on the filters"""
        # Clear the table
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Get the filter values
        date_from = self.date_from.get_date()  # This is a datetime.date object
        date_to = self.date_to.get_date()    # This is a datetime.date object
        category_filter_val = self.filter_category.get() # Renamed to avoid shadowing the module
        user_filter_val = self.filter_user.get()         # Renamed

        # Build the query
        query = """
            SELECT tasks.id, tasks.date, users.name, tasks.task_name, categories.name,
                tasks.hours_spent, tasks.start_time, tasks.end_time,
                tasks.priority, tasks.description
            FROM tasks
            JOIN categories ON tasks.category_id = categories.id
            LEFT JOIN users ON tasks.user_id = users.id
            WHERE tasks.date BETWEEN ? AND ?
        """
        params = [date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d")]

        # Add the category filter
        if category_filter_val != 'All':
            query += " AND categories.name = ?"
            params.append(category_filter_val)
        
        # Add the user filter
        if user_filter_val != 'All':
            query += " AND users.name = ?"
            params.append(user_filter_val)

        # Sorting
        query += " ORDER BY tasks.date DESC, tasks.start_time DESC"

        # Run the query
        cursor = self.db.conn.cursor()
        cursor.execute(query, params)
        fetched_rows = cursor.fetchall() # Fetch all rows at once

        # Tracking/grouping variables
        current_grouping_date_str = None # Date string used for grouping (e.g. "2023-10-27")
        daily_hours_sum = 0.0            # Sum of hours for the current day group
        tasks_in_day_group_count = 0     # Number of tasks in the current day group

        # Display counters and totals
        row_color_index = 0              # For alternating row colors (including totals)
        displayed_task_count = 0         # Row number for display (real tasks only)
        total_hours_for_period = 0.0     # Total hours for the whole filtered period

        for data_row_tuple in fetched_rows:
            displayed_task_count += 1 # Incremented for every real task

            # Extract the data from the row (data_row_tuple)
            task_id_from_db = data_row_tuple[0]
            task_date_from_db_str = data_row_tuple[1] # Date from the database as a string (YYYY-MM-DD)
            user_name_from_db = data_row_tuple[2]
            task_name_from_db = data_row_tuple[3]
            category_name_from_db = data_row_tuple[4]
            try:
                # Ensure hours is a float; default to 0.0 if None or invalid
                hours_spent_from_db = float(data_row_tuple[5]) if data_row_tuple[5] is not None else 0.0
            except ValueError:
                hours_spent_from_db = 0.0 # In case the conversion fails
            start_time_from_db = data_row_tuple[6] if data_row_tuple[6] is not None else ""
            end_time_from_db = data_row_tuple[7] if data_row_tuple[7] is not None else ""
            priority_from_db = data_row_tuple[8] if data_row_tuple[8] is not None else ""
            description_from_db = data_row_tuple[9] if len(data_row_tuple) > 9 and data_row_tuple[9] is not None else ""

            total_hours_for_period += hours_spent_from_db

            # Check whether a new day group has started
            if task_date_from_db_str != current_grouping_date_str:
                if current_grouping_date_str is not None: # If this isn't the first day in the loop
                    # Add the total row for the previous day
                    self.add_daily_total(current_grouping_date_str, daily_hours_sum, tasks_in_day_group_count)
                    row_color_index += 1 # The total row also affects the alternating color
                
                # Reset the values for the new day group
                current_grouping_date_str = task_date_from_db_str
                daily_hours_sum = 0.0
                tasks_in_day_group_count = 0

            # Accumulate data for the current day group
            daily_hours_sum += hours_spent_from_db
            tasks_in_day_group_count += 1

            # Prepare the values for the Treeview columns:
            # Row#, Date, User, Task, Category, Hours, Start, End, Priority, Actions
            values_for_tree_display = [
                displayed_task_count,
                task_date_from_db_str,
                user_name_from_db,
                task_name_from_db,
                category_name_from_db,
                f"{hours_spent_from_db:.2f}", # Hours formatted to two decimals
                start_time_from_db,
                end_time_from_db,
                priority_from_db,
                "Edit/Delete" # Text for the "Actions" column
            ]

            # Determine the row color (even/odd)
            tag_for_row_color = 'evenrow' if row_color_index % 2 == 0 else 'oddrow'

            # Build the row tags: (row_color, task_id_as_string, task_description)
            # This is required for right-click -> Edit/Delete to work correctly
            item_tags_for_tree = (tag_for_row_color, str(task_id_from_db), description_from_db)

            # Insert the row into the Treeview
            self.tree.insert("", "end", values=values_for_tree_display, tags=item_tags_for_tree)
            row_color_index += 1 # Bump the row counter that drives the alternating color

        # After the loop, add the total for the last day (if there was any data)
        if current_grouping_date_str is not None:
            self.add_daily_total(current_grouping_date_str, daily_hours_sum, tasks_in_day_group_count)
            row_color_index += 1 # This total row also affects the alternating color

        # Add the grand total for the whole filtered period
        # date_from/date_to are datetime.date objects from the filters at the top of the method
        self.add_period_total(date_from, date_to, total_hours_for_period)
        # row_color_index += 1; # Add this if you also want this row to affect the alternating color

        # Update the status bar
        # displayed_task_count only counts real tasks, which is correct for display
        self.status_text.set(f"Showing {displayed_task_count} tasks | Total hours: {total_hours_for_period:.2f}")

    def add_daily_total(self, date, hours, task_count):
        """Add a row with the daily total hours"""
        values = ["", date, "DAILY TOTAL", "", "", f"{hours:.2f}", "", "", "", ""]
        self.tree.insert("", "end", values=values, tags=('total',))
        self.tree.insert("", "end", values=["" for _ in range(10)], tags=('separator',))

    def add_period_total(self, date_from, date_to, hours):
        """Add a row with the total hours for the period"""
        period = f"{date_from.strftime('%d.%m.%Y')} - {date_to.strftime('%d.%m.%Y')}"
        values = ["", period, "PERIOD TOTAL", "", "", f"{hours:.2f}", "", "", "", ""]
        self.tree.insert("", "end", values=values, tags=('total',))

    def delete_task(self, task_id):
        """Delete a task from the database"""
        if messagebox.askyesno("Delete confirmation", "Are you sure you want to delete this task?"):
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                self.db.conn.commit()
                self.refresh_report()
                self.update_status_bar()
                messagebox.showinfo("Success", "Task deleted successfully!")
            except Exception as e:
                messagebox.showerror("Error", f"Error deleting task: {str(e)}")


    def show_edit_menu(self, event):
        """Show the context menu for editing/deleting a task"""
        # Identify the clicked row
        item_id = self.tree.identify_row(event.y) # identify_row returns the item ID

        if not item_id: # If no row was clicked
            return

        # Check whether this is a task row (not a total or separator)
        item_data = self.tree.item(item_id)
        tags = item_data.get('tags', []) # Get the tags, or an empty list if there are none

        # Check whether this is a task row based on its tags
        # Expected tags: (color, task_id, description)
        # Convert tags[1] to a string before calling .isdigit()
        if tags and len(tags) > 1 and str(tags[1]).isdigit(): # tags[1] should be the task_id
            self.tree.selection_set(item_id) # Select the row
            task_id_str = str(tags[1]) # Ensure task_id_str is a string

            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Edit Task",
                        command=lambda item=item_id, tid=task_id_str: self.edit_task(item, tid))
            menu.add_command(label="Delete Task",
                        command=lambda tid=task_id_str: self.delete_task(tid))
            menu.add_separator()
            menu.add_command(label="Show Details",
                        command=lambda item=item_id: self.show_task_details_from_item(item))
            menu.post(event.x_root, event.y_root)
        # else:
            # print(f"Debug: Clicked a row that isn't a task or has no valid ID. Tags: {tags}")

    def show_task_details_from_item(self, item_id):
        """Show task details based on the Treeview item_id"""
        if not item_id:
            return

        # Set the selection so the rest of show_task_details can rely on it
        # or use item_id directly to fetch the data
        self.tree.selection_set(item_id)
        self.show_task_details(event=None) # Call the original method, which uses self.tree.selection()
    

    def edit_task(self, item, task_id):
        """Open the task edit window"""
        task_values = self.tree.item(item)['values']
        description = self.tree.item(item)['tags'][2] if len(self.tree.item(item)['tags']) > 2 else ""

        edit_window = tk.Toplevel(self.root)
        edit_window.title("Edit Task")
        edit_window.geometry("600x450")
        edit_window.transient(self.root)
        edit_window.grab_set()

        # Main frame
        main_frame = ttk.Frame(edit_window, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Basic Info
        basic_frame = ttk.LabelFrame(main_frame, text="Basic Info", padding=10)
        basic_frame.pack(fill="x", pady=(0, 10))
        
        # Date
        date_frame = ttk.Frame(basic_frame)
        date_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(date_frame, text="Date:").pack(side=tk.LEFT)
        date_entry = DateEntry(date_frame, width=12)
        date_entry.set_date(datetime.strptime(task_values[1], '%Y-%m-%d').date())
        date_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # User
        user_frame = ttk.Frame(basic_frame)
        user_frame.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(user_frame, text="User:").pack(side=tk.LEFT)
        user_combo = ttk.Combobox(user_frame, width=20)
        user_combo['values'] = self.get_users()
        user_combo.set(task_values[2] or "")
        user_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Priority
        priority_frame = ttk.Frame(basic_frame)
        priority_frame.grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        ttk.Label(priority_frame, text="Priority:").pack(side=tk.LEFT)
        priority_combo = ttk.Combobox(priority_frame, width=10)
        priority_combo['values'] = ['High', 'Medium', 'Low']
        priority_combo.set(task_values[8] or "")
        priority_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Task name
        task_frame = ttk.Frame(basic_frame)
        task_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(task_frame, text="Task name:").pack(side=tk.LEFT)
        task_name_entry = ttk.Entry(task_frame, width=60)
        task_name_entry.insert(0, task_values[3])
        task_name_entry.pack(side=tk.LEFT, padx=(5, 0), fill="x", expand=True)
        
        # Category
        category_frame = ttk.Frame(basic_frame)
        category_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(category_frame, text="Category:").pack(side=tk.LEFT)
        category_combo = ttk.Combobox(category_frame, width=30)
        category_combo['values'] = self.get_categories()
        category_combo.set(task_values[4])
        category_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Grid configuration
        basic_frame.columnconfigure(0, weight=1)
        basic_frame.columnconfigure(1, weight=1)
        basic_frame.columnconfigure(2, weight=1)
        
        # Time frame
        time_frame = ttk.LabelFrame(main_frame, text="Time Tracking", padding=10)
        time_frame.pack(fill="x", pady=(0, 10))
        
        # Start time
        start_frame = ttk.Frame(time_frame)
        start_frame.pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Label(start_frame, text="Start (HH:MM):").pack(side=tk.LEFT)
        start_time_entry = ttk.Entry(start_frame, width=10)
        start_time_entry.insert(0, task_values[6] or '')
        start_time_entry.pack(side=tk.LEFT, padx=(5, 0))

        # End time
        end_frame = ttk.Frame(time_frame)
        end_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(end_frame, text="End (HH:MM):").pack(side=tk.LEFT)
        end_time_entry = ttk.Entry(end_frame, width=10)
        end_time_entry.insert(0, task_values[7] or '')
        end_time_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Number of hours
        hours_frame = ttk.Frame(time_frame)
        hours_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(hours_frame, text="Hours:").pack(side=tk.LEFT)
        hours_entry = ttk.Entry(hours_frame, width=10)
        hours_entry.insert(0, task_values[5])
        hours_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Description
        desc_frame = ttk.LabelFrame(main_frame, text="Task Description", padding=10)
        desc_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        desc_text = tk.Text(desc_frame, height=5, width=40)
        desc_text.insert("1.0", description)
        desc_text.pack(fill="both", expand=True)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(0, 5))

        def save_changes():
            try:
                # Validate required fields
                if not all([task_name_entry.get(), category_combo.get(), user_combo.get()]):
                    messagebox.showerror("Error", "Please fill in all required fields")
                    return

                # Validate hours
                try:
                    hours = float(hours_entry.get())
                    if hours <= 0:
                        raise ValueError("Hours must be a positive number")
                except ValueError:
                    messagebox.showerror("Error", "Enter a valid number of hours")
                    return

                cursor = self.db.conn.cursor()

                # Get the category ID
                cursor.execute("SELECT id FROM categories WHERE name = ?", (category_combo.get(),))
                category_id = cursor.fetchone()[0]

                # Get the user ID
                user_name = user_combo.get()
                cursor.execute("SELECT id FROM users WHERE name = ?", (user_name,))
                user_result = cursor.fetchone()

                if not user_result:
                    # If the user doesn't exist, add them
                    cursor.execute("INSERT INTO users (name) VALUES (?)", (user_name,))
                    self.db.conn.commit()
                    user_id = cursor.lastrowid
                else:
                    user_id = user_result[0]

                # Update the task
                cursor.execute("""
                    UPDATE tasks
                    SET date = ?, user_id = ?, category_id = ?, task_name = ?, description = ?,
                        hours_spent = ?, start_time = ?, end_time = ?, priority = ?
                    WHERE id = ?
                """, (
                    date_entry.get_date().strftime('%Y-%m-%d'),
                    user_id,
                    category_id,
                    task_name_entry.get(),
                    desc_text.get("1.0", tk.END).strip(),
                    hours,
                    start_time_entry.get(),
                    end_time_entry.get(),
                    priority_combo.get(),
                    task_id
                ))
                self.db.conn.commit()

                # Update the report and status bar
                self.refresh_report()
                self.update_status_bar()

                edit_window.destroy()
                messagebox.showinfo("Success", "Task updated successfully!")

            except Exception as e:
                messagebox.showerror("Error", f"Error updating task: {str(e)}")
                # Log the error
                print(f"Error updating task: {str(e)}")

        ttk.Button(button_frame, text="Save Changes",
                 command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel",
                 command=edit_window.destroy).pack(side=tk.RIGHT, padx=5)

    def show_task_details(self, event):
        """Show task details"""
        if event:  # If invoked from an event
            item = self.tree.identify_row(event.y)
            if not item:
                return
            self.tree.selection_set(item)

        # Get the selected row
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        task_values = self.tree.item(item)['values']

        # Check whether this is a totals row
        if not task_values or "TOTAL" in str(task_values):
            return

        # Create the details window
        details_window = tk.Toplevel(self.root)
        details_window.title("Task Details")
        details_window.geometry("500x400")
        details_window.transient(self.root)

        # Main frame
        main_frame = ttk.Frame(details_window, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Basic Info
        info_frame = ttk.LabelFrame(main_frame, text="Task Information", padding=10)
        info_frame.pack(fill="x", pady=(0, 10))

        # Build the data table
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill="x")

        # Row 1
        ttk.Label(info_grid, text="Date:", font=('', 9, 'bold')).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[1]).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(info_grid, text="User:", font=('', 9, 'bold')).grid(row=0, column=2, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[2] or "").grid(row=0, column=3, sticky="w", padx=5, pady=2)

        # Row 2
        ttk.Label(info_grid, text="Task:", font=('', 9, 'bold')).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[3], wraplength=350).grid(row=1, column=1, columnspan=3, sticky="w", padx=5, pady=2)

        # Row 3
        ttk.Label(info_grid, text="Category:", font=('', 9, 'bold')).grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[4]).grid(row=2, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(info_grid, text="Priority:", font=('', 9, 'bold')).grid(row=2, column=2, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[8] or "").grid(row=2, column=3, sticky="w", padx=5, pady=2)

        # Row 4
        ttk.Label(info_grid, text="Time:", font=('', 9, 'bold')).grid(row=3, column=0, sticky="w", padx=5, pady=2)
        time_text = f"{task_values[6] or ''} - {task_values[7] or ''}"
        ttk.Label(info_grid, text=time_text).grid(row=3, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(info_grid, text="Hours:", font=('', 9, 'bold')).grid(row=3, column=2, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[5]).grid(row=3, column=3, sticky="w", padx=5, pady=2)

        # Description
        desc_frame = ttk.LabelFrame(main_frame, text="Description", padding=10)
        desc_frame.pack(fill="both", expand=True)

        desc_text = tk.Text(desc_frame, wrap=tk.WORD, padx=10, pady=10)
        desc_text.insert("1.0", self.tree.item(item)['tags'][2] if len(self.tree.item(item)['tags']) > 2 else "No description")
        desc_text.config(state="disabled")

        # Add scrollbars
        scrollbar = ttk.Scrollbar(desc_frame, orient="vertical", command=desc_text.yview)
        desc_text.configure(yscrollcommand=scrollbar.set)

        desc_text.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))

        # Get the task ID
        task_id = self.tree.item(item)['tags'][1] if len(self.tree.item(item)['tags']) > 1 else None

        if task_id and str(task_id.isdigit()):
            ttk.Button(button_frame, text="Edit",
                     command=lambda: [details_window.destroy(), self.edit_task(item, task_id)]).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Delete",
                     command=lambda: [details_window.destroy(), self.delete_task(task_id)]).pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Close",
                 command=details_window.destroy).pack(side=tk.RIGHT, padx=5)

    def show_statistics(self):
        """Show statistics for the selected period"""
        # Clear existing data
        for item in self.cat_tree.get_children():
            self.cat_tree.delete(item)
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)

        # Get the filter values
        date_from = self.stats_date_from.get_date()
        date_to = self.stats_date_to.get_date()

        # Statistics by category
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT categories.name, SUM(tasks.hours_spent) as total_hours
            FROM tasks
            JOIN categories ON tasks.category_id = categories.id
            WHERE tasks.date BETWEEN ? AND ?
            GROUP BY categories.name
            ORDER BY total_hours DESC
        """, (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

        category_stats = cursor.fetchall()

        # Calculate the total hours
        total_hours = sum(row[1] for row in category_stats)

        # Populate the category table
        for i, (category, hours) in enumerate(category_stats):
            percentage = (hours / total_hours * 100) if total_hours > 0 else 0
            self.cat_tree.insert("", tk.END, values=(category, f"{hours:.2f}", f"{percentage:.1f}%"),
                               tags=('oddrow' if i % 2 else 'evenrow'))

        # Add the total
        self.cat_tree.insert("", tk.END, values=("TOTAL", f"{total_hours:.2f}", "100.0%"),
                           tags=('total',))

        # Statistics by user
        cursor.execute("""
            SELECT users.name, SUM(tasks.hours_spent) as total_hours
            FROM tasks
            LEFT JOIN users ON tasks.user_id = users.id
            WHERE tasks.date BETWEEN ? AND ?
            GROUP BY users.name
            ORDER BY total_hours DESC
        """, (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

        user_stats = cursor.fetchall()

        # Populate the user table
        for i, (user, hours) in enumerate(user_stats):
            percentage = (hours / total_hours * 100) if total_hours > 0 else 0
            self.user_tree.insert("", tk.END, values=(user or "Unknown", f"{hours:.2f}", f"{percentage:.1f}%"),
                                tags=('oddrow' if i % 2 else 'evenrow'))

        # Add the total
        self.user_tree.insert("", tk.END, values=("TOTAL", f"{total_hours:.2f}", "100.0%"),
                            tags=('total',))

    def export_to_excel(self):
        """Export the report (Reports tab) to Excel."""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            if not file_path:
                return

            data = []
            for item_id in self.tree.get_children():
                item = self.tree.item(item_id)
                values = item["values"]
                tags = item["tags"]

                if 'total' in tags or 'separator' in tags or not values:
                    continue
                if len(tags) > 1 and str(tags[1]).isdigit():
                    task_data_row = list(values[1:9])
                    try:
                        hours_value = float(task_data_row[4])
                    except (ValueError, TypeError):
                        hours_value = 0.0
                    task_data_row[4] = hours_value
                    data.append(task_data_row)

            if not data:
                messagebox.showinfo("Info", "No data to export.")
                return

            export.write_task_report(file_path, data)
            messagebox.showinfo("Success", "Report exported successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Error exporting to Excel: {str(e)}")
            print(f"Error exporting to Excel: {str(e)}")

    def export_statistics(self):
        """Export the statistics (Stats tab) to Excel."""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
            )
            if not file_path:
                return

            date_from = self.stats_date_from.get_date()
            date_to = self.stats_date_to.get_date()
            params = (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d'))

            cursor = self.db.conn.cursor()

            cursor.execute("""
                SELECT categories.name, SUM(tasks.hours_spent) as total_hours
                FROM tasks
                JOIN categories ON tasks.category_id = categories.id
                WHERE tasks.date BETWEEN ? AND ?
                GROUP BY categories.name
                ORDER BY total_hours DESC
            """, params)
            category_stats = cursor.fetchall()

            cursor.execute("""
                SELECT users.name, SUM(tasks.hours_spent) as total_hours
                FROM tasks
                LEFT JOIN users ON tasks.user_id = users.id
                WHERE tasks.date BETWEEN ? AND ?
                GROUP BY users.name
                ORDER BY total_hours DESC
            """, params)
            user_stats = cursor.fetchall()

            cursor.execute("""
                SELECT tasks.date, categories.name, users.name, SUM(tasks.hours_spent) as total_hours
                FROM tasks
                JOIN categories ON tasks.category_id = categories.id
                LEFT JOIN users ON tasks.user_id = users.id
                WHERE tasks.date BETWEEN ? AND ?
                GROUP BY tasks.date, categories.name, users.name
                ORDER BY tasks.date DESC, total_hours DESC
            """, params)
            daily_stats = cursor.fetchall()

            cursor.execute("""
                SELECT tasks.date, users.name, categories.name, tasks.task_name,
                       tasks.hours_spent, tasks.start_time, tasks.end_time, tasks.priority,
                       tasks.description
                FROM tasks
                JOIN categories ON tasks.category_id = categories.id
                LEFT JOIN users ON tasks.user_id = users.id
                WHERE tasks.date BETWEEN ? AND ?
                ORDER BY tasks.date DESC, tasks.start_time DESC
            """, params)
            details = cursor.fetchall()

            export.write_statistics_report(file_path, category_stats, user_stats, daily_stats, details)
            messagebox.showinfo("Success", "Statistics exported successfully!")

        except Exception as e:
            messagebox.showerror("Error", f"Error exporting statistics: {str(e)}")
            print(f"Error exporting statistics: {str(e)}")

    def refresh_future_tasks(self):
        """Refresh the future tasks list"""
        try:
            # Clear the table
            for item in self.future_tree.get_children():
                self.future_tree.delete(item)

            # Get the filter values
            date_from_obj = self.future_date_from.get_date()
            date_to_obj = self.future_date_to.get_date()
            user_filter_val = self.future_user_filter.get()
            category_filter_val = self.future_category_filter.get()

            query = """
                SELECT ft.id, ft.date, u.name, ft.task_name, c.name, ft.priority,
                    CASE ft.completed WHEN 1 THEN 'Completed' ELSE 'Active' END as status,
                    ft.description
                FROM future_tasks ft
                LEFT JOIN users u ON ft.user_id = u.id
                LEFT JOIN categories c ON ft.category_id = c.id
                WHERE ft.date BETWEEN ? AND ?
            """
            params = [date_from_obj.strftime('%Y-%m-%d'), date_to_obj.strftime('%Y-%m-%d')]

            if user_filter_val != 'All':
                query += " AND u.name = ?"
                params.append(user_filter_val)
            if category_filter_val != 'All':
                query += " AND c.name = ?"
                params.append(category_filter_val)

            query += " ORDER BY ft.date ASC, ft.priority DESC" # Maybe a different sort order?

            cursor = self.db.conn.cursor()
            cursor.execute(query, params)
            fetched_rows = cursor.fetchall()

            row_color_index = 0
            task_display_count = 0
            for row_data in fetched_rows:
                task_display_count += 1
                future_task_id_db = row_data[0]
                # Display values: #, Date, User, Task, Category, Priority, Status
                # row_data[0] is the ID, row_data[1] is the Date, ..., row_data[6] is the Status
                # row_data[7] is the description, not shown directly but needed for the tag
                display_values = [task_display_count] + list(row_data[1:7])

                tag_for_row_color = 'evenrow' if row_color_index % 2 == 0 else 'oddrow'
                description_val = row_data[7] if len(row_data) > 7 and row_data[7] is not None else ""

                # Correct tagging: (color, task_id_as_string, description)
                item_tags = (tag_for_row_color, str(future_task_id_db), description_val)

                self.future_tree.insert("", "end", values=display_values, tags=item_tags)
                row_color_index += 1

        except Exception as e:
            messagebox.showerror("Error", f"Error refreshing future tasks: {str(e)}")
            print(f"Error refreshing future tasks: {str(e)}")

    def get_all_users(self):
        """Returns the list of all users"""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM users ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

    def get_all_categories(self):
            """Returns the list of all categories"""
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT name FROM categories ORDER BY name")
            return [row[0] for row in cursor.fetchall()]
    

    def show_future_task_details(self, event): # event may be None
        """Show future task details in a new window"""
        item_id_tk = None
        if event is not None: # Called from a double-click
            selected_item_tuple = self.future_tree.selection()
            if not selected_item_tuple: return
            item_id_tk = selected_item_tuple[0]
        else: # Called from the context menu
            selected_item_tuple = self.future_tree.selection()
            if not selected_item_tuple: return
            item_id_tk = selected_item_tuple[0]

        if not item_id_tk: return

        item_data = self.future_tree.item(item_id_tk)
        tags = item_data.get('tags', [])

        # Convert tags[1] to a string before calling .isdigit()
        if not (tags and len(tags) > 1 and tags[1] is not None and str(tags[1]).isdigit()):
            # print(f"Debug show_future_task_details: Not a task row or missing a valid ID. Tags: {tags}")
            return

        future_task_id_for_db = int(str(tags[1])) # Convert to int for the query

        try:
            cursor = self.db.conn.cursor()
            cursor.execute("""
                SELECT ft.date, u.name, ft.task_name, c.name, ft.priority, ft.description, ft.completed
                FROM future_tasks ft
                LEFT JOIN users u ON ft.user_id = u.id
                LEFT JOIN categories c ON ft.category_id = c.id
                WHERE ft.id = ?
            """, (future_task_id_for_db,))
            task = cursor.fetchone()

            if not task:
                messagebox.showerror("Error", "Future task details not found.")
                return

            details_window = tk.Toplevel(self.root)
            details_window.title("Future Task Details")
            details_window.geometry("500x400") # Slightly shorter since there's no hours/time
            details_window.transient(self.root)
            details_window.grab_set()

            main_frame = ttk.Frame(details_window, padding=15)
            main_frame.pack(fill="both", expand=True)

            fields = [
                ("Date:", task[0]),
                ("User:", task[1] if task[1] else "N/A"),
                ("Task:", task[2]),
                ("Category:", task[3] if task[3] else "N/A"),
                ("Priority:", task[4] if task[4] else "N/A"),
                ("Status:", "Completed" if task[6] == 1 else "Active (planned)")
            ]

            for i, (label_text, value_text) in enumerate(fields):
                ttk.Label(main_frame, text=label_text, font=('TkDefaultFont', 10, 'bold')).grid(row=i, column=0, sticky="ne", pady=3, padx=5)
                if label_text == "Task:":
                    task_name_label = ttk.Label(main_frame, text=value_text if value_text else "N/A", wraplength=300, justify=tk.LEFT)
                    task_name_label.grid(row=i, column=1, sticky="nw", pady=3, padx=5)
                else:
                    ttk.Label(main_frame, text=value_text if value_text else "N/A").grid(row=i, column=1, sticky="nw", pady=3, padx=5)


            ttk.Label(main_frame, text="Description:", font=('TkDefaultFont', 10, 'bold')).grid(row=len(fields), column=0, sticky="ne", pady=(10,3), padx=5)
            desc_frame = ttk.Frame(main_frame)
            desc_frame.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="nsew", pady=2, padx=5)
            desc_frame.grid_columnconfigure(0, weight=1)
            desc_frame.grid_rowconfigure(0, weight=1)

            desc_text_widget = tk.Text(desc_frame, height=5, width=50, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1)
            desc_text_widget.insert(tk.END, task[5] if task[5] else "No description.")
            desc_text_widget.config(state=tk.DISABLED)
            desc_text_widget.pack(side=tk.LEFT, fill="both", expand=True, pady=2, padx=2)

            desc_scrollbar = ttk.Scrollbar(desc_frame, orient="vertical", command=desc_text_widget.yview)
            desc_scrollbar.pack(side=tk.RIGHT, fill="y")
            desc_text_widget.config(yscrollcommand=desc_scrollbar.set)
            main_frame.grid_rowconfigure(len(fields) + 1, weight=1)


            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=len(fields) + 2, column=0, columnspan=2, pady=(15,5))

            ttk.Button(button_frame, text="Move to Entry",
                    command=lambda: (self.prepare_future_task_for_entry(str(future_task_id_for_db)), details_window.destroy())).pack(side=tk.LEFT, padx=5)
            if task[6] == 0: # If not completed (completed == 0)
                ttk.Button(button_frame, text="Mark as Completed",
                        command=lambda: (self.mark_future_task_completed(str(future_task_id_for_db)), details_window.destroy())).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Delete",
                    command=lambda: (self.delete_future_task(str(future_task_id_for_db)), details_window.destroy())).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Close", command=details_window.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Error", f"Error displaying future task details: {str(e)}")
            print(f"Error showing future task details: {str(e)}")

    def show_future_task_context_menu(self, event):
        """Show the future task context menu"""
        item_id = self.future_tree.identify_row(event.y)
        if not item_id:
            return

        item_data = self.future_tree.item(item_id)
        tags = item_data.get('tags', []) # tags should be (color, future_task_id_str, description)

        # Convert tags[1] to a string before calling .isdigit()
        if tags and len(tags) > 1 and tags[1] is not None and str(tags[1]).isdigit():
            self.future_tree.selection_set(item_id)
            future_task_id_str = str(tags[1]) # Ensure future_task_id_str is a string

            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Show Details",
                        command=lambda item=item_id: self.show_future_task_details_from_item(item))
            menu.add_command(label="Move to Entry (as active)",
                        command=lambda ftid=future_task_id_str: self.prepare_future_task_for_entry(ftid))
            menu.add_separator()
            menu.add_command(label="Mark as Completed (and remove)",
                        command=lambda ftid=future_task_id_str: self.mark_future_task_completed(ftid))
            menu.add_command(label="Delete Future Task",
                        command=lambda ftid=future_task_id_str: self.delete_future_task(ftid))
            menu.post(event.x_root, event.y_root)
        # else:
            # print(f"Debug show_future_task_context_menu: Not a task row or missing a valid ID. Tags: {tags}")

    def show_future_task_details_from_item(self, item_id):
        if not item_id:
            return
        self.future_tree.selection_set(item_id) # Set the selection
        self.show_future_task_details(event=None) # Call the original method
        

    def mark_future_task_completed(self, future_task_id_str):
        """Marks a future task as completed (removes it from the list)."""
        if not messagebox.askyesno("Confirm", "Are you sure you want to mark this task as completed and remove it from the future tasks list?"):
            return
        try:
            future_task_id = int(future_task_id_str)
            cursor = self.db.conn.cursor()
            cursor.execute("DELETE FROM future_tasks WHERE id = ?", (future_task_id,))
            self.db.conn.commit()
            messagebox.showinfo("Success", "Future task marked as completed and removed.")
            self.refresh_future_tasks()
        except ValueError:
            messagebox.showerror("Error", "Invalid task ID.")
        except Exception as e:
            messagebox.showerror("Error", f"Error marking task as completed: {str(e)}")

    def delete_future_task(self, task_id=None):
        """Delete a future task"""
        if not task_id:
            selection = self.future_tree.selection()
            if not selection:
                messagebox.showinfo("Information", "Please select a task")
                return

            item = selection[0]
            task_id = self.future_tree.item(item)['tags'][0]

        # Delete confirmation
        if not messagebox.askyesno("Confirm", "Are you sure you want to delete this task?"):
            return

        # Delete the task
        cursor = self.db.conn.cursor()
        cursor.execute("DELETE FROM future_tasks WHERE id = ?", (task_id,))
        self.db.conn.commit()

        # Refresh the list
        self.refresh_future_tasks()
        messagebox.showinfo("Success", "Task deleted successfully") 
    

    def run(self):
        """Run the application's main loop."""
        try:
            today = datetime.now().date()
            self.date_from.set_date(today - timedelta(days=2))
            self.date_to.set_date(today)

            self.refresh_future_tasks()
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror("Critical Error", f"A critical error occurred: {str(e)}")
