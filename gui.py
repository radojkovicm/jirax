"""Tkinter GUI for JiraX Time Tracker."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from tkcalendar import DateEntry
import locale
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
            print("Ikona 'time_tracker.ico' nije pronadjena ili je neispravna.")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=5, pady=5)

        self.task_frame = ttk.Frame(self.notebook)
        self.report_frame = ttk.Frame(self.notebook)
        self.stats_frame = ttk.Frame(self.notebook)
        self.future_tasks_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.task_frame, text='Unos zadatka')
        self.notebook.add(self.report_frame, text='Reports')
        self.notebook.add(self.stats_frame, text='Stats')
        self.notebook.add(self.future_tasks_frame, text="Budući zadaci")
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
        """Poziva se kada korisnik promeni aktivni tab."""
        try:
            selected_tab_widget = self.notebook.nametowidget(self.notebook.select())
            # Možemo proveriti koji je frame selektovan
            if selected_tab_widget == self.report_frame:
                # print("Debug: Reports tab je selektovan, pozivam refresh_report.")
                self.refresh_report()
            elif selected_tab_widget == self.future_tasks_frame:
                self.refresh_future_tasks()
            elif selected_tab_widget == self.stats_frame:
                self.show_statistics()
            # Za task_frame obično nije potrebno automatsko osvežavanje pri selekciji
        except tk.TclError:
            # Ovo se može desiti ako se notebook još uvek inicijalizuje
            # print("Debug: TclError u on_tab_changed, verovatno tokom inicijalizacije.")
            pass
        except Exception as e:
            print(f"Greška u on_tab_changed: {e}")

    def update_status_bar(self):
        # Izračunavanje ukupnih sati za danas, ovu nedelju i ovaj mesec
        today = datetime.now().date()
        week_start = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)
        
        cursor = self.db.conn.cursor()
        
        # Sati za danas
        cursor.execute("""
            SELECT SUM(hours_spent) FROM tasks 
            WHERE date = ?
        """, (today.strftime('%Y-%m-%d'),))
        today_hours = cursor.fetchone()[0] or 0
        
        # Sati za ovu nedelju
        cursor.execute("""
            SELECT SUM(hours_spent) FROM tasks 
            WHERE date BETWEEN ? AND ?
        """, (week_start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')))
        week_hours = cursor.fetchone()[0] or 0
        
        # Sati za ovaj mesec
        cursor.execute("""
            SELECT SUM(hours_spent) FROM tasks 
            WHERE date BETWEEN ? AND ?
        """, (month_start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d')))
        month_hours = cursor.fetchone()[0] or 0
        
        self.total_hours_today = today_hours
        self.total_hours_week = week_hours
        self.total_hours_month = month_hours
        
        # Ažuriranje statusne trake
        self.status_text.set(f"Spremno | Baza: {os.path.abspath('time_tracker.db')}")
        self.hours_text.set(f"Danas: {today_hours:.2f}h | Nedelja: {week_hours:.2f}h | Mesec: {month_hours:.2f}h")

    def get_categories(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM categories ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

    def get_users(self):
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM users ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

    def setup_task_entry(self):
        # Glavni okvir za unos zadatka
        main_frame = ttk.Frame(self.task_frame, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Gornji deo - osnovni podaci
        basic_frame = ttk.LabelFrame(main_frame, text="Osnovni podaci", padding=10)
        basic_frame.pack(fill="x", pady=(0, 10))
        
        # Datum
        date_frame = ttk.Frame(basic_frame)
        date_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(date_frame, text="Datum:").pack(side=tk.LEFT)
        self.date_entry = DateEntry(date_frame, width=12, background='darkblue',
                                  foreground='white', borderwidth=2)
        self.date_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Korisnik (novo)
        user_frame = ttk.Frame(basic_frame)
        user_frame.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(user_frame, text="Korisnik:").pack(side=tk.LEFT)
        self.user_entry = ttk.Combobox(user_frame, width=20)
        self.user_entry['values'] = self.get_users()
        self.user_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.user_entry.bind('<KeyRelease>', self.update_user_suggestions)
        
        # Prioritet
        priority_frame = ttk.Frame(basic_frame)
        priority_frame.grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        ttk.Label(priority_frame, text="Prioritet:").pack(side=tk.LEFT)
        self.priority_combo = ttk.Combobox(priority_frame, width=10)
        self.priority_combo['values'] = ['Visok', 'Srednji', 'Nizak']
        self.priority_combo.pack(side=tk.LEFT, padx=(5, 0))
        self.priority_combo.set('Srednji')
        
        # Naziv zadatka
        task_frame = ttk.Frame(basic_frame)
        task_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(task_frame, text="Naziv zadatka:").pack(side=tk.LEFT)
        self.task_entry = ttk.Combobox(task_frame, width=60)
        self.task_entry.pack(side=tk.LEFT, padx=(5, 0), fill="x", expand=True)
        self.task_entry.bind('<KeyRelease>', self.update_task_suggestions)
        
        # Kategorija
        category_frame = ttk.Frame(basic_frame)
        category_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(category_frame, text="Kategorija:").pack(side=tk.LEFT)
        self.category_combo = ttk.Combobox(category_frame, width=30)
        self.category_combo['values'] = self.get_categories()
        self.category_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Konfiguracija mreže
        basic_frame.columnconfigure(0, weight=1)
        basic_frame.columnconfigure(1, weight=1)
        basic_frame.columnconfigure(2, weight=1)
        
        # Okvir za vreme
        time_frame = ttk.LabelFrame(main_frame, text="Praćenje vremena", padding=10)
        time_frame.pack(fill="x", pady=(0, 10))
        
        # Početno vreme
        start_frame = ttk.Frame(time_frame)
        start_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(start_frame, text="Početak (HH:MM):").pack(side=tk.LEFT)
        self.start_time = tk.StringVar()
        self.start_entry = ttk.Entry(start_frame, textvariable=self.start_time, width=10)
        self.start_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.start_entry.bind('<KeyRelease>', self.calculate_hours)
        self.start_entry.bind('<FocusOut>', self.validate_time_format)
        
        # Završno vreme
        end_frame = ttk.Frame(time_frame)
        end_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(end_frame, text="Kraj (HH:MM):").pack(side=tk.LEFT)
        self.end_time = tk.StringVar()
        self.end_entry = ttk.Entry(end_frame, textvariable=self.end_time, width=10)
        self.end_entry.pack(side=tk.LEFT, padx=(5, 0))
        self.end_entry.bind('<KeyRelease>', self.calculate_hours)
        self.end_entry.bind('<FocusOut>', self.validate_time_format)
        
        # Broj sati
        hours_frame = ttk.Frame(time_frame)
        hours_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(hours_frame, text="Sati:").pack(side=tk.LEFT)
        self.hours_entry = ttk.Entry(hours_frame, width=10)
        self.hours_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Dugme za trenutno vreme
        now_button = ttk.Button(time_frame, text="Trenutno vreme", 
                              command=self.set_current_time)
        now_button.pack(side=tk.RIGHT, padx=5, pady=5)
        
        # Opis
        desc_frame = ttk.LabelFrame(main_frame, text="Opis zadatka", padding=10)
        desc_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.desc_text = tk.Text(desc_frame, height=5, width=40)
        self.desc_text.pack(fill="both", expand=True)

        # OVDE dodajte checkbox za buduće zadatke
        checkbox_frame = ttk.Frame(main_frame)
        checkbox_frame.pack(fill="x", pady=(0, 5))

        # Checkbox za buduće zadatke
        self.future_task_var = tk.BooleanVar()
        self.future_task_check = ttk.Checkbutton(checkbox_frame, text="Budući zadatak",
                                                variable=self.future_task_var)
        self.future_task_check.pack(side=tk.LEFT, padx=5)

        # Checkbox za označavanje zadatka kao završenog (samo za buduće zadatke)
        self.completed_var = tk.BooleanVar()
        self.completed_check = ttk.Checkbutton(checkbox_frame, text="Završen",
                                            variable=self.completed_var)
        self.completed_check.pack(side=tk.LEFT, padx=5)
        self.completed_check.grid_remove()  # Sakriveno po defaultu

        # Povezivanje promene stanja checkbox-a sa funkcijom
        self.future_task_var.trace_add("write", lambda *args: self.toggle_completed_checkbox())
        
        # Dugmad
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(0, 5))
        
        ttk.Button(button_frame, text="Sačuvaj zadatak", 
                 command=self.save_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Sačuvaj kao predložak", 
                 command=self.save_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Učitaj predložak", 
                 command=self.load_template).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Kopiraj poslednji zadatak", 
                 command=self.copy_last_task).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Očisti polja", 
                 command=self.clear_fields).pack(side=tk.RIGHT, padx=5)

    # ... unutar klase TimeTracker ...

    def setup_report_tab(self):
        # Glavni okvir za izveštaje
        main_report_frame = ttk.Frame(self.report_frame, padding=10)
        main_report_frame.pack(fill="both", expand=True)

        # Okvir za filtere
        filter_frame = ttk.LabelFrame(main_report_frame, text="Filteri", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))

        # ... (ostatak koda za filtere: date_from, date_to, filter_category, filter_user, refresh_button) ...
        # (Ovaj deo je već bio tu i trebalo bi da je ispravan)

        # Datum od
        from_frame = ttk.Frame(filter_frame)
        from_frame.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(from_frame, text="Od:").pack(side=tk.LEFT)
        self.date_from = DateEntry(from_frame, width=12, background='darkblue',
                                foreground='white', borderwidth=2, date_pattern='dd.MM.yyyy')
        self.date_from.pack(side=tk.LEFT, padx=(5,0))

        # Datum do
        to_frame = ttk.Frame(filter_frame)
        to_frame.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(to_frame, text="Do:").pack(side=tk.LEFT)
        self.date_to = DateEntry(to_frame, width=12, background='darkblue',
                                foreground='white', borderwidth=2, date_pattern='dd.MM.yyyy')
        self.date_to.pack(side=tk.LEFT, padx=(5,0))

        # Kategorija filter
        category_filter_frame = ttk.Frame(filter_frame)
        category_filter_frame.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Label(category_filter_frame, text="Kategorija:").pack(side=tk.LEFT)
        self.filter_category = ttk.Combobox(category_filter_frame, width=15)
        self.filter_category['values'] = ['Sve'] + self.get_categories()
        self.filter_category.current(0)
        self.filter_category.pack(side=tk.LEFT, padx=(5,0))

        # Korisnik filter
        user_filter_frame = ttk.Frame(filter_frame)
        user_filter_frame.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(user_filter_frame, text="Korisnik:").pack(side=tk.LEFT)
        self.filter_user = ttk.Combobox(user_filter_frame, width=15)
        self.filter_user['values'] = ['Svi'] + self.get_users()
        self.filter_user.current(0)
        self.filter_user.pack(side=tk.LEFT, padx=(5,0))

        # Dugme za osvežavanje i izvoz
        buttons_frame = ttk.Frame(filter_frame)
        buttons_frame.grid(row=0, column=4, padx=5, pady=5, sticky="e")
        ttk.Button(buttons_frame, text="Osveži", command=self.refresh_report).pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(buttons_frame, text="Izvezi u Excel", command=self.export_to_excel).pack(side=tk.LEFT)

        filter_frame.columnconfigure(4, weight=1) # Da se dugmad gurnu desno

        # Okvir za Treeview
        tree_view_frame = ttk.Frame(main_report_frame)
        tree_view_frame.pack(fill="both", expand=True, pady=(10,0))

        # Kreiranje Treeview-a
        self.tree = ttk.Treeview(tree_view_frame, columns=("#", "Datum", "Korisnik", "Zadatak", "Kategorija",
                                                        "Sati", "Početak", "Kraj", "Prioritet", "Akcije"),
                                show="headings")
        # ... (definicije kolona za self.tree) ...
        self.tree.heading("#", text="#")
        self.tree.heading("Datum", text="Datum")
        self.tree.heading("Korisnik", text="Korisnik")
        self.tree.heading("Zadatak", text="Zadatak")
        self.tree.heading("Kategorija", text="Kategorija")
        self.tree.heading("Sati", text="Sati")
        self.tree.heading("Početak", text="Početak")
        self.tree.heading("Kraj", text="Kraj")
        self.tree.heading("Prioritet", text="Prioritet")
        self.tree.heading("Akcije", text="Akcije")

        self.tree.column("#", width=30, anchor="center")
        self.tree.column("Datum", width=100, anchor="center")
        self.tree.column("Korisnik", width=120)
        self.tree.column("Zadatak", width=250)
        self.tree.column("Kategorija", width=120)
        self.tree.column("Sati", width=60, anchor="e")
        self.tree.column("Početak", width=70, anchor="center")
        self.tree.column("Kraj", width=70, anchor="center")
        self.tree.column("Prioritet", width=80, anchor="center")
        self.tree.column("Akcije", width=100, anchor="center")


        # Dodavanje klizača
        vsb = ttk.Scrollbar(tree_view_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tree_view_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        tree_view_frame.grid_columnconfigure(0, weight=1)
        tree_view_frame.grid_rowconfigure(0, weight=1)

        # Povezivanje događaja
        self.tree.bind("<Double-1>", self.show_task_details)
        self.tree.bind("<Button-3>", self.show_edit_menu) # <<< DODAJTE/PROVERITE OVU LINIJU

        # Stilovi za redove
        self.tree.tag_configure('oddrow', background='#f0f0f0')
        self.tree.tag_configure('evenrow', background='white')
        self.tree.tag_configure('total', background='#e0e0e0', font=('TkDefaultFont', 10, 'bold'))
        self.tree.tag_configure('separator', background='gray')

    def setup_stats_tab(self):
        # Glavni okvir za statistiku
        main_frame = ttk.Frame(self.stats_frame, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Okvir za filtere
        filter_frame = ttk.LabelFrame(main_frame, text="Period", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))
        
        # Datum od
        from_frame = ttk.Frame(filter_frame)
        from_frame.grid(row=0, column=0, padx=5, pady=5)
        
        ttk.Label(from_frame, text="Od:").pack(side=tk.LEFT)
        self.stats_date_from = DateEntry(from_frame, width=12)
        self.stats_date_from.set_date(datetime.now().date().replace(day=1))  # Prvi dan u mesecu
        self.stats_date_from.pack(side=tk.LEFT, padx=(5, 0))
        
        # Datum do
        to_frame = ttk.Frame(filter_frame)
        to_frame.grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(to_frame, text="Do:").pack(side=tk.LEFT)
        self.stats_date_to = DateEntry(to_frame, width=12)
        self.stats_date_to.pack(side=tk.LEFT, padx=(5, 0))
        
        # Dugmad
        button_frame = ttk.Frame(filter_frame)
        button_frame.grid(row=0, column=2, padx=5, pady=5)
        
        ttk.Button(button_frame, text="Prikaži statistiku", 
                 command=self.show_statistics).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Izvezi statistiku", 
                 command=self.export_statistics).pack(side=tk.LEFT, padx=5)
        
        # Konfiguracija mreže
        filter_frame.columnconfigure(0, weight=1)
        filter_frame.columnconfigure(1, weight=1)
        filter_frame.columnconfigure(2, weight=2)
        
        # Okvir za prikaz statistike
        stats_display_frame = ttk.Frame(main_frame)
        stats_display_frame.pack(fill="both", expand=True)
        
        # Levi panel - statistika po kategorijama
        cat_frame = ttk.LabelFrame(stats_display_frame, text="Po kategorijama", padding=10)
        cat_frame.pack(side=tk.LEFT, fill="both", expand=True, padx=(0, 5))
        
        self.cat_tree = ttk.Treeview(cat_frame, columns=("Category", "Hours", "Percentage"),
                                   show="headings")
        self.cat_tree.heading("Category", text="Kategorija")
        self.cat_tree.heading("Hours", text="Sati")
        self.cat_tree.heading("Percentage", text="%")
        
        self.cat_tree.column("Category", width=150)
        self.cat_tree.column("Hours", width=70, anchor="center")
        self.cat_tree.column("Percentage", width=70, anchor="center")
        
        self.cat_tree.pack(fill="both", expand=True)
        
        # Desni panel - statistika po korisnicima
        user_frame = ttk.LabelFrame(stats_display_frame, text="Po korisnicima", padding=10)
        user_frame.pack(side=tk.RIGHT, fill="both", expand=True, padx=(5, 0))
        
        self.user_tree = ttk.Treeview(user_frame, columns=("User", "Hours", "Percentage"),
                                    show="headings")
        self.user_tree.heading("User", text="Korisnik")
        self.user_tree.heading("Hours", text="Sati")
        self.user_tree.heading("Percentage", text="%")
        
        self.user_tree.column("User", width=150)
        self.user_tree.column("Hours", width=70, anchor="center")
        self.user_tree.column("Percentage", width=70, anchor="center")
        
        self.user_tree.pack(fill="both", expand=True)
        

    def setup_future_tasks_tab(self, parent_frame):
        # Glavni okvir za buduće zadatke unutar parent_frame (koji je future_frame)
        main_future_frame = ttk.Frame(parent_frame, padding=10)
        main_future_frame.pack(fill="both", expand=True)

        # Okvir za filtere
        filter_frame = ttk.LabelFrame(main_future_frame, text="Filteri za buduće zadatke", padding=10)
        filter_frame.pack(fill="x", pady=(0, 10))

        # Datum od
        future_from_frame = ttk.Frame(filter_frame)
        future_from_frame.grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ttk.Label(future_from_frame, text="Od:").pack(side=tk.LEFT)
        self.future_date_from = DateEntry(future_from_frame, width=12, background='darkblue',
                                        foreground='white', borderwidth=2, date_pattern='dd.MM.yyyy')
        self.future_date_from.set_date(self.future_date_from_value) # Koristi vrednost iz __init__
        self.future_date_from.pack(side=tk.LEFT, padx=(5, 0))

        # Datum do
        future_to_frame = ttk.Frame(filter_frame)
        future_to_frame.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(future_to_frame, text="Do:").pack(side=tk.LEFT)
        self.future_date_to = DateEntry(future_to_frame, width=12, background='darkblue',
                                        foreground='white', borderwidth=2, date_pattern='dd.MM.yyyy')
        self.future_date_to.set_date(self.future_date_to_value) # Koristi vrednost iz __init__
        self.future_date_to.pack(side=tk.LEFT, padx=(5, 0))

        # Korisnik filter
        future_user_filter_frame = ttk.Frame(filter_frame)
        future_user_filter_frame.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ttk.Label(future_user_filter_frame, text="Korisnik:").pack(side=tk.LEFT)
        self.future_user_filter = ttk.Combobox(future_user_filter_frame, width=15)
        self.future_user_filter['values'] = ['Svi'] + self.get_all_users()
        self.future_user_filter.current(0)
        self.future_user_filter.pack(side=tk.LEFT, padx=(5, 0))

        # Kategorija filter
        future_category_filter_frame = ttk.Frame(filter_frame)
        future_category_filter_frame.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ttk.Label(future_category_filter_frame, text="Kategorija:").pack(side=tk.LEFT)
        self.future_category_filter = ttk.Combobox(future_category_filter_frame, width=15)
        self.future_category_filter['values'] = ['Sve'] + self.get_all_categories()
        self.future_category_filter.current(0)
        self.future_category_filter.pack(side=tk.LEFT, padx=(5, 0))

        # Dugme za osvežavanje
        refresh_button_frame = ttk.Frame(filter_frame)
        refresh_button_frame.grid(row=0, column=4, padx=5, pady=5, sticky="e")
        ttk.Button(refresh_button_frame, text="Osveži", command=self.refresh_future_tasks).pack(side=tk.LEFT)

        filter_frame.columnconfigure(4, weight=1) # Da se dugme gurne desno ako ima prostora

        # Okvir za Treeview
        tree_view_frame = ttk.Frame(main_future_frame)
        tree_view_frame.pack(fill="both", expand=True, pady=(10,0))

        # Kreiranje Treeview-a za buduće zadatke
        self.future_tree = ttk.Treeview(tree_view_frame, columns=("#", "Datum", "Korisnik", "Zadatak", "Kategorija", "Prioritet", "Status"),
                                    show="headings")
        self.future_tree.heading("#", text="#")
        self.future_tree.heading("Datum", text="Datum")
        self.future_tree.heading("Korisnik", text="Korisnik")
        self.future_tree.heading("Zadatak", text="Zadatak")
        self.future_tree.heading("Kategorija", text="Kategorija")
        self.future_tree.heading("Prioritet", text="Prioritet")
        self.future_tree.heading("Status", text="Status")

        self.future_tree.column("#", width=30, anchor="center")
        self.future_tree.column("Datum", width=100, anchor="center")
        self.future_tree.column("Korisnik", width=120)
        self.future_tree.column("Zadatak", width=250)
        self.future_tree.column("Kategorija", width=120)
        self.future_tree.column("Prioritet", width=80, anchor="center")
        self.future_tree.column("Status", width=100, anchor="center")

        # Dodavanje klizača
        vsb_future = ttk.Scrollbar(tree_view_frame, orient="vertical", command=self.future_tree.yview)
        hsb_future = ttk.Scrollbar(tree_view_frame, orient="horizontal", command=self.future_tree.xview)
        self.future_tree.configure(yscrollcommand=vsb_future.set, xscrollcommand=hsb_future.set)

        self.future_tree.grid(row=0, column=0, sticky="nsew")
        vsb_future.grid(row=0, column=1, sticky="ns")
        hsb_future.grid(row=1, column=0, sticky="ew")

        tree_view_frame.grid_columnconfigure(0, weight=1)
        tree_view_frame.grid_rowconfigure(0, weight=1)

        # ... unutar metode setup_future_tasks_tab(self, parent_frame) ...

        # Povezivanje događaja
        self.future_tree.bind("<Double-1>", self.show_future_task_details)
        self.future_tree.bind("<Button-3>", self.show_future_task_context_menu) # KLJUČNA LINIJA

        # Stilovi za redove (opciono, ako želite različite boje za parne/neparne redove)
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
        
        # Dobijanje predloga iz zadataka
        cursor.execute("""
            SELECT DISTINCT task_name 
            FROM tasks 
            WHERE LOWER(task_name) LIKE ? 
            ORDER BY id DESC LIMIT 10
        """, (f"%{current_text}%",))
        
        db_suggestions = [row[0] for row in cursor.fetchall()]
        
        # Dobijanje predloga iz predložaka
        cursor.execute("""
            SELECT DISTINCT task_name 
            FROM templates 
            WHERE LOWER(task_name) LIKE ? 
            ORDER BY id DESC LIMIT 5
        """, (f"%{current_text}%",))
        
        template_suggestions = [row[0] for row in cursor.fetchall()]
        
        # Kombinovanje i uklanjanje duplikata
        all_suggestions = list(dict.fromkeys(db_suggestions + template_suggestions))[:10]
        
        if all_suggestions:
            self.task_entry['values'] = all_suggestions
            
            if len(all_suggestions) == 1 and all_suggestions[0].lower() == current_text:
                self.task_entry.selection_clear()
            else:
                if not self.task_entry.winfo_ismapped():
                    self.task_entry.event_generate('<Down>')

    def validate_time_format(self, event=None):
        """Validacija formata vremena (HH:MM)"""
        widget = event.widget
        time_str = widget.get()
        
        if not time_str:
            return
        
        try:
            # Provera formata
            if len(time_str) != 5 or time_str[2] != ':':
                raise ValueError("Neispravan format")
            
            hours, minutes = map(int, time_str.split(':'))
            
            if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
                raise ValueError("Neispravno vreme")
                
        except ValueError:
            messagebox.showerror("Greška", "Neispravan format vremena. Koristite HH:MM (npr. 09:30)")
            widget.delete(0, tk.END)
            widget.focus_set()

    def calculate_hours(self, event=None):
        """Izračunavanje broja sati između početnog i završnog vremena"""
        try:
            start = self.start_time.get()
            end = self.end_time.get()
            
            if start and end and len(start) == 5 and len(end) == 5:
                start_dt = datetime.strptime(start, '%H:%M')
                end_dt = datetime.strptime(end, '%H:%M')
                
                # Ako je završno vreme pre početnog, pretpostavljamo da je sledeći dan
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                    
                diff = end_dt - start_dt
                hours = diff.total_seconds() / 3600
                
                self.hours_entry.delete(0, tk.END)
                self.hours_entry.insert(0, f"{hours:.2f}")
        except ValueError:
            pass

    # ... unutar klase TimeTracker ...

    def set_current_time(self):
        """Postavlja početno vreme na kraj poslednjeg zadatka za dati dan, ili 08:00."""
        selected_date_str = self.date_entry.get_date().strftime('%Y-%m-%d')
        # selected_user_name = self.user_entry.get() # Razmisliti da li treba filtrirati po korisniku

        cursor = self.db.conn.cursor()

        # Pronađi poslednje end_time za izabrani datum
        # Možete dodati i user_id u WHERE klauzulu ako želite da bude specifično za korisnika
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

        next_start_time_str = "08:00" # Podrazumevano vreme

        if last_task_end_time and last_task_end_time[0]:
            # Proveri da li je format HH:MM
            try:
                datetime.strptime(last_task_end_time[0], '%H:%M')
                next_start_time_str = last_task_end_time[0]
            except ValueError:
                # Ako format nije dobar, koristi podrazumevano
                print(f"Warning: Neispravan format end_time '{last_task_end_time[0]}' u bazi, koristim 08:00.")
                pass # next_start_time_str ostaje "08:00"

        self.start_time.set(next_start_time_str)
        self.end_time.set("")  # Očisti krajnje vreme
        self.hours_entry.delete(0, tk.END) # Očisti sate
        self.start_entry.focus_set() # Fokusiraj se na unos početnog vremena
        # Nema potrebe za calculate_hours() ovde jer je end_time prazno

    def clear_fields(self):
        """Čišćenje svih polja za unos"""
        self.task_entry.set('')
        self.desc_text.delete("1.0", tk.END)
        self.hours_entry.delete(0, tk.END)
        self.start_time.set('')
        self.end_time.set('')
        self.priority_combo.set('Srednji')
        # Ne čistimo datum i korisnika jer su to često iste vrednosti
        

    def toggle_completed_checkbox(self):
        if self.future_task_var.get():
            self.completed_check.pack()  # Prikazujemo checkbox za završen
            # Sakrivamo polja za vreme
            self.hours_entry.config(state=tk.DISABLED)
            self.start_entry.config(state=tk.DISABLED)
            self.end_entry.config(state=tk.DISABLED)
        else:
            self.completed_check.pack_forget()  # Sakrivamo checkbox za završen
            # Prikazujemo polja za vreme
            self.hours_entry.config(state=tk.NORMAL)
            self.start_entry.config(state=tk.NORMAL)
            self.end_entry.config(state=tk.NORMAL)

    # ... unutar klase TimeTracker ...
    # ... unutar klase TimeTracker ...

    def prepare_future_task_for_entry(self, future_task_id_str):
        """Priprema budući zadatak za unos u tab 'Unos zadatka'."""
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
                messagebox.showerror("Greška", "Budući zadatak nije pronađen.")
                return

            # Raspakivanje podataka
            task_date_str, user_name, task_name, category_name, description, priority = task_data

            # Popunjavanje polja u 'Unos zadatka' tabu
            self.date_entry.set_date(datetime.now().date())

            self.user_entry.set(user_name if user_name else "")
            self.task_entry.set(task_name if task_name else "") # self.task_entry je verovatno ime widgeta
            self.category_combo.set(category_name if category_name else "")
            self.desc_text.delete("1.0", tk.END)
            self.desc_text.insert("1.0", description if description else "")
            self.priority_combo.set(priority if priority else "Srednji")

            self.start_time.set("")
            self.end_time.set("")
            self.hours_entry.delete(0, tk.END)

            self.future_task_var.set(False)
            self.completed_var.set(False)

            self.prefilling_from_future_task_id = future_task_id

            self.notebook.select(self.task_frame)
            # ISPRAVLJENA LINIJA:
            # Pretpostavka je da se widget za unos naziva zadatka zove self.task_entry
            if hasattr(self, 'task_entry') and self.task_entry:
                self.task_entry.focus_set()
            # Ako ste ga nazvali drugačije (npr. self.task_name_entry), koristite to ime:
            # elif hasattr(self, 'task_name_entry') and self.task_name_entry:
            #     self.task_name_entry.focus_set()
            else:
                print("Upozorenje: Polje za unos naziva zadatka (task_entry) nije pronađeno za postavljanje fokusa.")


            messagebox.showinfo("Informacija", "Detalji budućeg zadatka su popunjeni. Unesite vreme i sačuvajte kao aktivni zadatak.")

        except ValueError:
            messagebox.showerror("Greška", "Nevažeći ID budućeg zadatka.")
        except Exception as e:
            messagebox.showerror("Greška", f"Greška pri pripremi zadatka za unos: {str(e)}")
            print(f"Error preparing future task for entry: {str(e)}")
        

    def save_task(self):
        """Čuvanje novog zadatka u bazi podataka"""
        try:
            # ... (početak metode save_task, prikupljanje podataka, validacija - ostaje isto) ...
            date_str = self.date_entry.get_date().strftime('%Y-%m-%d')
            user = self.user_entry.get()
            task_name = self.task_entry.get()
            category = self.category_combo.get()
            description = self.desc_text.get("1.0", tk.END).strip()
            priority_val = self.priority_combo.get()
            is_future_task_checkbox = self.future_task_var.get() # Preimenovano da se ne meša sa is_future_task logikom
            hours = 0.0
            start_time_str = ""
            end_time_str = ""

            if not all([task_name, category, user]):
                messagebox.showerror("Greška", "Molimo popunite sva obavezna polja (korisnik, zadatak, kategorija)")
                return

            if not is_future_task_checkbox: # Ako NIJE označen checkbox "Budući zadatak"
                # Validacija sati i prikupljanje vremena samo za REGULARNE zadatke
                # ... (logika za validaciju sati i vremena, kao što je bila) ...
                if not self.hours_entry.get() and (not self.start_time.get() or not self.end_time.get()):
                    messagebox.showerror("Greška", "Za aktivni zadatak, unesite broj sati ili vreme početka i kraja.")
                    return
                try:
                    if self.hours_entry.get():
                        hours = float(self.hours_entry.get())
                        if hours <= 0:
                            raise ValueError("Sati moraju biti pozitivan broj")
                    elif self.start_time.get() and self.end_time.get():
                        self.calculate_hours()
                        if self.hours_entry.get():
                            hours = float(self.hours_entry.get())
                            if hours <= 0:
                                if not (datetime.strptime(self.end_time.get(), '%H:%M') < datetime.strptime(self.start_time.get(), '%H:%M')):
                                    messagebox.showerror("Greška", "Neispravan unos sati. Proverite vreme početka i kraja ili unesite sate direktno.")
                                    return
                        else:
                            messagebox.showerror("Greška", "Unesite ispravan broj sati ili vreme početka i kraja.")
                            return
                    else:
                        messagebox.showerror("Greška", "Unesite broj sati ili vreme početka i kraja za aktivni zadatak.")
                        return
                except ValueError:
                    messagebox.showerror("Greška", "Unesite ispravan broj sati.")
                    return
                start_time_str = self.start_time.get()
                end_time_str = self.end_time.get()
            # else: Za budući zadatak, sati i vreme nisu potrebni

            cursor = self.db.conn.cursor()
            # ... (logika za dobijanje/dodavanje category_id i user_id - ostaje ista) ...
            # Provera i dodavanje kategorije ako ne postoji
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
                messagebox.showerror("Greška", "Molimo unesite kategoriju")
                return

            # Provera i dodavanje korisnika ako ne postoji
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
                messagebox.showerror("Greška", "Molimo unesite korisnika")
                return


            if is_future_task_checkbox: # Ako je checkbox "Budući zadatak" označen
                # Čuvanje NOVOG budućeg zadatka
                cursor.execute("""
                    INSERT INTO future_tasks (date, user_id, category_id, task_name, description, priority, completed)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str, user_id, category_id, task_name, description, priority_val,
                    1 if self.completed_var.get() else 0
                ))
                self.db.conn.commit()
                messagebox.showinfo("Uspeh", "Budući zadatak uspešno sačuvan!")
                self.refresh_future_tasks()
            else: # Ako NIJE označen checkbox "Budući zadatak" -> čuvamo kao AKTIVNI zadatak
                cursor.execute("""
                    INSERT INTO tasks (date, user_id, category_id, task_name, description,
                                    hours_spent, start_time, end_time, priority)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str, user_id, category_id, task_name, description,
                    hours, start_time_str, end_time_str, priority_val
                ))
                self.db.conn.commit()
                messagebox.showinfo("Uspeh", "Aktivni zadatak uspešno sačuvan!")

                # Ako je ovaj aktivni zadatak rezultat prebacivanja iz budućih zadataka,
                # obriši originalni budući zadatak
                if self.prefilling_from_future_task_id is not None:
                    try:
                        cursor.execute("DELETE FROM future_tasks WHERE id = ?", (self.prefilling_from_future_task_id,))
                        self.db.conn.commit()
                        print(f"Debug: Obrisao budući zadatak sa ID: {self.prefilling_from_future_task_id}")
                        self.prefilling_from_future_task_id = None # Resetuj ID
                        self.refresh_future_tasks() # Osveži listu budućih zadataka
                    except Exception as e_del:
                        print(f"Greška pri brisanju originalnog budućeg zadatka: {e_del}")
                        messagebox.showwarning("Upozorenje", f"Zadatak je sačuvan kao aktivni, ali je došlo do greške pri brisanju originalnog budućeg zadatka: {e_del}")


            # Ažuriranje nedavnih zadataka i korisnika
            self.recent_tasks.add(task_name)
            self.recent_users.add(user)

            # Ažuriranje izveštaja i statusne trake
            self.refresh_report()
            self.update_status_bar()
            self._update_filter_comboboxes()

            # Čišćenje polja
            self.task_entry.set('')
            self.desc_text.delete("1.0", tk.END)
            self.hours_entry.delete(0, tk.END)
            self.start_time.set('')
            self.end_time.set('')
            # Ne čistimo korisnika i kategoriju odmah, možda korisnik želi da unese više zadataka za istog
            self.category_combo.set('')
            self.user_entry.set('')
            self.priority_combo.set('Srednji')
            self.future_task_var.set(False)
            self.completed_var.set(False)

            # Ako NIJE bilo prebacivanja iz budućeg zadatka, resetuj ID za svaki slučaj
            # (iako bi trebalo da je None ako nije bilo prebacivanja)
            if not is_future_task_checkbox and self.prefilling_from_future_task_id is not None:
                # Ovo se dešava ako je korisnik kliknuo "Prebaci", pa onda označio "Budući zadatak" i sačuvao.
                # U tom slučaju, ne treba brisati originalni. Resetujemo samo ako je sačuvan kao AKTIVAN.
                pass # Već je obrađeno gore
            elif self.prefilling_from_future_task_id is not None and is_future_task_checkbox:
                # Korisnik je prebacio, ali onda odlučio da ga ipak sačuva kao NOVI budući zadatak.
                # U tom slučaju, ne diramo originalni, samo resetujemo flag.
                self.prefilling_from_future_task_id = None


        except Exception as e:
            messagebox.showerror("Greška", f"Greška pri čuvanju zadatka: {str(e)}")
            print(f"Error saving task: {str(e)}")
            # Ako je došlo do greške, a prefilling_from_future_task_id je postavljen,
            # možda ga ne treba resetovati da korisnik može da pokuša ponovo bez ponovnog prebacivanja.
            # Ili ga resetovati da se izbegne neočekivano ponašanje pri sledećem čuvanju.
            # Za sada, nećemo ga dirati ovde u except bloku.

    def _update_filter_comboboxes(self):
        """Ažurira vrednosti u svim Combobox filterima za kategorije i korisnike."""
        all_categories = self.get_categories()
        all_users = self.get_users()

        # Sačuvaj trenutno selektovane vrednosti da pokušaš da ih vratiš
        current_filter_cat = self.filter_category.get()
        current_filter_user = self.filter_user.get()
        current_future_cat = self.future_category_filter.get()
        current_future_user = self.future_user_filter.get()
        current_task_cat = self.category_combo.get() # Za unos zadatka
        current_task_user = self.user_entry.get() # Za unos zadatka


        # Report Tab filters
        self.filter_category['values'] = ['Sve'] + all_categories
        if current_filter_cat in self.filter_category['values']:
            self.filter_category.set(current_filter_cat)
        elif self.filter_category['values']:
            self.filter_category.current(0) # Vrati na "Sve" ako prethodna vrednost više ne postoji

        self.filter_user['values'] = ['Svi'] + all_users
        if current_filter_user in self.filter_user['values']:
            self.filter_user.set(current_filter_user)
        elif self.filter_user['values']:
            self.filter_user.current(0) # Vrati na "Svi"

        # Future Tasks Tab filters
        # get_all_categories i get_all_users su iste kao get_categories i get_users
        self.future_category_filter['values'] = ['Sve'] + all_categories
        if current_future_cat in self.future_category_filter['values']:
            self.future_category_filter.set(current_future_cat)
        elif self.future_category_filter['values']:
            self.future_category_filter.current(0)

        self.future_user_filter['values'] = ['Svi'] + all_users
        if current_future_user in self.future_user_filter['values']:
            self.future_user_filter.set(current_future_user)
        elif self.future_user_filter['values']:
            self.future_user_filter.current(0)

        # Task Entry Tab (ako se dodaju nove kategorije/korisnici direktno)
        self.category_combo['values'] = all_categories
        if current_task_cat in self.category_combo['values']:
            self.category_combo.set(current_task_cat)
        # else: self.category_combo.set('') # Ili ostavi prazno

        self.user_entry['values'] = all_users
        if current_task_user in self.user_entry['values']:
            self.user_entry.set(current_task_user)
        else: self.user_entry.set('') # Ili ostavi prazno
    

    def load_templates(self):
        """Učitavanje svih predložaka iz baze"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT templates.task_name, users.name, categories.name, templates.description 
            FROM templates 
            JOIN categories ON templates.category_id = categories.id
            LEFT JOIN users ON templates.user_id = users.id
        """)
        return cursor.fetchall()

    def save_template(self):
        """Čuvanje trenutnog zadatka kao predložak"""
        task_name = self.task_entry.get()
        user = self.user_entry.get()
        category = self.category_combo.get()
        description = self.desc_text.get("1.0", tk.END).strip()

        if not task_name or not category:
            messagebox.showerror("Greška", "Molimo popunite naziv zadatka i kategoriju")
            return

        try:
            cursor = self.db.conn.cursor()
            
            # Dobijanje ID-a kategorije
            cursor.execute("SELECT id FROM categories WHERE name = ?", (category,))
            category_result = cursor.fetchone()
            if not category_result:
                messagebox.showerror("Greška", f"Kategorija '{category}' ne postoji")
                return
            category_id = category_result[0]
            
            # Dobijanje ID-a korisnika
            user_id = None
            if user:
                cursor.execute("SELECT id FROM users WHERE name = ?", (user,))
                user_result = cursor.fetchone()
                if not user_result:
                    # Ako korisnik ne postoji, dodajemo ga
                    cursor.execute("INSERT INTO users (name) VALUES (?)", (user,))
                    self.db.conn.commit()
                    user_id = cursor.lastrowid
                else:
                    user_id = user_result[0]

            # Provera da li predložak već postoji
            cursor.execute("""
                SELECT id FROM templates 
                WHERE task_name = ? AND category_id = ? AND 
                      (user_id = ? OR (user_id IS NULL AND ? IS NULL))
            """, (task_name, category_id, user_id, user_id))
            
            existing = cursor.fetchone()
            if existing:
                if messagebox.askyesno("Upozorenje", "Predložak sa istim nazivom već postoji. Želite li da ga zamenite?"):
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
            self._update_filter_comboboxes() # <<< DODAJTE OVAJ RED
            messagebox.showinfo("Uspeh", "Predložak uspešno sačuvan!")

        except Exception as e:
            messagebox.showerror("Greška", f"Greška pri čuvanju predloška: {str(e)}")
            # Logovanje greške
            print(f"Error saving template: {str(e)}")

    def load_template(self):
        """Učitavanje predloška iz baze"""
        if not self.task_templates:
            messagebox.showinfo("Info", "Nema dostupnih predložaka")
            return

        template_window = tk.Toplevel(self.root)
        template_window.title("Učitaj predložak")
        template_window.geometry("500x400")
        template_window.transient(self.root)
        template_window.grab_set()

        # Okvir za pretragu
        search_frame = ttk.Frame(template_window, padding=5)
        search_frame.pack(fill="x")
        
        ttk.Label(search_frame, text="Pretraga:").pack(side=tk.LEFT)
        search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5, fill="x", expand=True)
        
        # Lista predložaka
        template_frame = ttk.Frame(template_window)
        template_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        template_list = ttk.Treeview(template_frame, columns=("Task", "User", "Category"), 
                                   show="headings", height=15)
        template_list.heading("Task", text="Naziv zadatka")
        template_list.heading("User", text="Korisnik")
        template_list.heading("Category", text="Kategorija")
        
        template_list.column("Task", width=200)
        template_list.column("User", width=100)
        template_list.column("Category", width=150)
        
        vsb = ttk.Scrollbar(template_frame, orient="vertical", command=template_list.yview)
        template_list.configure(yscrollcommand=vsb.set)
        
        template_list.pack(side=tk.LEFT, fill="both", expand=True)
        vsb.pack(side=tk.RIGHT, fill="y")
        
        # Opis predloška
        desc_frame = ttk.LabelFrame(template_window, text="Opis", padding=5)
        desc_frame.pack(fill="x", padx=5, pady=5)
        
        desc_text = tk.Text(desc_frame, height=5, width=40, wrap=tk.WORD)
        desc_text.pack(fill="both", expand=True)
        desc_text.config(state=tk.DISABLED)
        
        # Dugmad
        button_frame = ttk.Frame(template_window, padding=5)
        button_frame.pack(fill="x")
        
        ttk.Button(button_frame, text="Primeni", 
                 command=lambda: apply_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Obriši predložak", 
                 command=lambda: delete_template()).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Otkaži", 
                 command=template_window.destroy).pack(side=tk.RIGHT, padx=5)
        
        # Popunjavanje liste predložaka
        def populate_templates(search_text=""):
            template_list.delete(*template_list.get_children())
            search_text = search_text.lower()
            
            for template in self.task_templates:
                task_name, user_name, category_name, description = template
                
                if (search_text in task_name.lower() or 
                    (user_name and search_text in user_name.lower()) or 
                    search_text in category_name.lower()):
                    template_list.insert("", tk.END, values=(task_name, user_name or "", category_name))
        
        # Prikaz opisa predloška
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
        
        # Primena predloška
        def apply_template():
            selection = template_list.selection()
            if not selection:
                messagebox.showinfo("Info", "Molimo izaberite predložak")
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
        
        # Brisanje predloška
        def delete_template():
            selection = template_list.selection()
            if not selection:
                messagebox.showinfo("Info", "Molimo izaberite predložak")
                return
            
            if not messagebox.askyesno("Potvrda", "Da li ste sigurni da želite da obrišete ovaj predložak?"):
                return
            
            selected = template_list.item(selection[0])['values']
            task_name, user_name, category_name = selected
            
            try:
                cursor = self.db.conn.cursor()
                
                # Dobijanje ID-a kategorije
                cursor.execute("SELECT id FROM categories WHERE name = ?", (category_name,))
                category_id = cursor.fetchone()[0]
                
                # Dobijanje ID-a korisnika
                user_id = None
                if user_name:
                    cursor.execute("SELECT id FROM users WHERE name = ?", (user_name,))
                    user_result = cursor.fetchone()
                    if user_result:
                        user_id = user_result[0]
                
                # Brisanje predloška
                cursor.execute("""
                    DELETE FROM templates 
                    WHERE task_name = ? AND category_id = ? AND 
                          (user_id = ? OR (user_id IS NULL AND ? IS NULL))
                """, (task_name, category_id, user_id, user_id))
                
                self.db.conn.commit()
                self.task_templates = self.load_templates()
                
                populate_templates(search_var.get())
                messagebox.showinfo("Uspeh", "Predložak uspešno obrisan!")
                
            except Exception as e:
                messagebox.showerror("Greška", f"Greška pri brisanju predloška: {str(e)}")
        
        # Pretraga predložaka
        def search_templates(*args):
            populate_templates(search_var.get())
        
        search_var.trace("w", search_templates)
        template_list.bind('<Double-1>', lambda e: apply_template())
        template_list.bind('<<TreeviewSelect>>', show_description)
        
        # Inicijalno popunjavanje
        populate_templates()
        
        # Fokus na polje za pretragu
        search_entry.focus_set()

    def copy_last_task(self):
        """Kopiranje poslednjeg unetog zadatka"""
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
            messagebox.showinfo("Info", "Nema prethodnih zadataka")

    def refresh_report(self):
        """Osvežavanje izveštaja prema filterima"""
        # Čišćenje tabele
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Dobijanje vrednosti filtera
        date_from = self.date_from.get_date()  # Ovo je datetime.date objekat
        date_to = self.date_to.get_date()    # Ovo je datetime.date objekat
        category_filter_val = self.filter_category.get() # Preimenovano da se izbegne konflikt sa modulom
        user_filter_val = self.filter_user.get()         # Preimenovano

        # Kreiranje upita
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

        # Dodavanje filtera za kategoriju
        if category_filter_val != 'Sve':
            query += " AND categories.name = ?"
            params.append(category_filter_val)
        
        # Dodavanje filtera za korisnika
        if user_filter_val != 'Svi':
            query += " AND users.name = ?"
            params.append(user_filter_val)

        # Sortiranje
        query += " ORDER BY tasks.date DESC, tasks.start_time DESC"

        # Izvršavanje upita
        cursor = self.db.conn.cursor()
        cursor.execute(query, params)
        fetched_rows = cursor.fetchall() # Pribavi sve redove odjednom

        # Varijable za praćenje i grupisanje
        current_grouping_date_str = None # String datuma za grupisanje (npr. "2023-10-27")
        daily_hours_sum = 0.0            # Suma sati za trenutni dan u grupi
        tasks_in_day_group_count = 0     # Broj zadataka u trenutnoj dnevnoj grupi

        # Brojači za prikaz i ukupne vrednosti
        row_color_index = 0              # Za naizmenično bojenje redova (uključujući totale)
        displayed_task_count = 0         # Redni broj zadatka za prikaz u tabeli (samo za stvarne zadatke)
        total_hours_for_period = 0.0     # Ukupni sati za ceo filtrirani period

        for data_row_tuple in fetched_rows:
            displayed_task_count += 1 # Inkrementira se za svaki stvarni zadatak

            # Ekstrakcija podataka iz reda (data_row_tuple)
            task_id_from_db = data_row_tuple[0]
            task_date_from_db_str = data_row_tuple[1] # Datum iz baze kao string (YYYY-MM-DD)
            user_name_from_db = data_row_tuple[2]
            task_name_from_db = data_row_tuple[3]
            category_name_from_db = data_row_tuple[4]
            try:
                # Osiguravamo da su sati float; ako je None ili nevalidno, postavi na 0.0
                hours_spent_from_db = float(data_row_tuple[5]) if data_row_tuple[5] is not None else 0.0
            except ValueError:
                hours_spent_from_db = 0.0 # U slučaju greške pri konverziji
            start_time_from_db = data_row_tuple[6] if data_row_tuple[6] is not None else ""
            end_time_from_db = data_row_tuple[7] if data_row_tuple[7] is not None else ""
            priority_from_db = data_row_tuple[8] if data_row_tuple[8] is not None else ""
            description_from_db = data_row_tuple[9] if len(data_row_tuple) > 9 and data_row_tuple[9] is not None else ""

            total_hours_for_period += hours_spent_from_db

            # Provera da li je počeo novi dan za grupisanje
            if task_date_from_db_str != current_grouping_date_str:
                if current_grouping_date_str is not None: # Ako ovo nije prvi dan u iteraciji
                    # Dodaj total za prethodno završeni dan
                    self.add_daily_total(current_grouping_date_str, daily_hours_sum, tasks_in_day_group_count)
                    row_color_index += 1 # Red za total takođe utiče na bojenje
                
                # Resetuj vrednosti za novi dan grupisanja
                current_grouping_date_str = task_date_from_db_str
                daily_hours_sum = 0.0
                tasks_in_day_group_count = 0

            # Akumuliraj podatke za trenutni dan grupisanja
            daily_hours_sum += hours_spent_from_db
            tasks_in_day_group_count += 1

            # Priprema vrednosti za prikaz u Treeview kolone:
            # RedniBroj, Datum, Korisnik, Zadatak, Kategorija, Sati, Start, End, Prioritet, Akcije
            values_for_tree_display = [
                displayed_task_count,
                task_date_from_db_str,
                user_name_from_db,
                task_name_from_db,
                category_name_from_db,
                f"{hours_spent_from_db:.2f}", # Formatirani sati na dve decimale
                start_time_from_db,
                end_time_from_db,
                priority_from_db,
                "Izmeni/Obriši" # Tekst za "Akcije" kolonu
            ]

            # Određivanje boje reda (parni/neparni)
            tag_for_row_color = 'evenrow' if row_color_index % 2 == 0 else 'oddrow'

            # Kreiranje tagova za red: (boja_reda, ID_zadatka_kao_string, opis_zadatka)
            # Ovo je ključno da bi desni klik -> Izmeni/Obriši radilo ispravno
            item_tags_for_tree = (tag_for_row_color, str(task_id_from_db), description_from_db)

            # Unos reda u Treeview
            self.tree.insert("", "end", values=values_for_tree_display, tags=item_tags_for_tree)
            row_color_index += 1 # Inkrementiraj brojač redova koji utiče na bojenje

        # Nakon završetka petlje, dodaj total za poslednji dan (ako je bilo podataka)
        if current_grouping_date_str is not None:
            self.add_daily_total(current_grouping_date_str, daily_hours_sum, tasks_in_day_group_count)
            row_color_index += 1 # I ovaj total red utiče na bojenje

        # Dodavanje ukupnog zbira za ceo filtrirani period
        # date_from i date_to su datetime.date objekti dobijeni iz filtera na početku metode
        self.add_period_total(date_from, date_to, total_hours_for_period)
        # row_color_index += 1; # Možete dodati ako želite da i ovaj red utiče na bojenje

        # Ažuriranje statusne trake
        # displayed_task_count broji samo stvarne zadatke, što je ispravno za prikaz
        self.status_text.set(f"Prikazano {displayed_task_count} zadataka | Ukupno sati: {total_hours_for_period:.2f}")

    def add_daily_total(self, date, hours, task_count):
        """Dodavanje reda sa dnevnim ukupnim satima"""
        values = ["", date, "DNEVNO UKUPNO", "", "", f"{hours:.2f}", "", "", "", ""]
        self.tree.insert("", "end", values=values, tags=('total',))
        self.tree.insert("", "end", values=["" for _ in range(10)], tags=('separator',))

    def add_period_total(self, date_from, date_to, hours):
        """Dodavanje reda sa ukupnim satima za period"""
        period = f"{date_from.strftime('%d.%m.%Y')} - {date_to.strftime('%d.%m.%Y')}"
        values = ["", period, "UKUPNO ZA PERIOD", "", "", f"{hours:.2f}", "", "", "", ""]
        self.tree.insert("", "end", values=values, tags=('total',))

    def delete_task(self, task_id):
        """Brisanje zadatka iz baze"""
        if messagebox.askyesno("Potvrda brisanja", "Da li ste sigurni da želite da obrišete ovaj zadatak?"):
            try:
                cursor = self.db.conn.cursor()
                cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                self.db.conn.commit()
                self.refresh_report()
                self.update_status_bar()
                messagebox.showinfo("Uspeh", "Zadatak uspešno obrisan!")
            except Exception as e:
                messagebox.showerror("Greška", f"Greška pri brisanju zadatka: {str(e)}")

    # ... unutar klase TimeTracker ...

    def show_edit_menu(self, event):
        """Prikaz kontekstnog menija za izmenu/brisanje zadatka"""
        # Identifikuj red na koji je kliknuto
        item_id = self.tree.identify_row(event.y) # identify_row vraća ID itema

        if not item_id: # Ako nije kliknuto na red
            return

        # Proveri da li je red sa podacima o zadatku (ne totali ili separatori)
        item_data = self.tree.item(item_id)
        tags = item_data.get('tags', []) # Uzmi tagove, ako ne postoje, vrati praznu listu

        # Proveravamo da li je ovo red sa zadatkom na osnovu tagova
        # Očekujemo da tagovi budu (boja, task_id, opis)
        # KORIGOVANA LINIJA: Konvertujemo tags[1] u string pre poziva .isdigit()
        if tags and len(tags) > 1 and str(tags[1]).isdigit(): # tags[1] bi trebao biti task_id
            self.tree.selection_set(item_id) # Selektuj red
            task_id_str = str(tags[1]) # Osiguravamo da je task_id_str string

            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Izmeni zadatak",
                        command=lambda item=item_id, tid=task_id_str: self.edit_task(item, tid))
            menu.add_command(label="Obriši zadatak",
                        command=lambda tid=task_id_str: self.delete_task(tid))
            menu.add_separator()
            menu.add_command(label="Prikaži detalje",
                        command=lambda item=item_id: self.show_task_details_from_item(item))
            menu.post(event.x_root, event.y_root)
        # else:
            # print(f"Debug: Kliknuto na red koji nije zadatak ili nema validan ID. Tags: {tags}")

    def show_task_details_from_item(self, item_id):
        """Prikaz detalja o zadatku na osnovu item_id iz Treeview-a"""
        if not item_id:
            return

        # Postavi selekciju da bi ostatak logike u show_task_details mogao da radi ako se oslanja na nju
        # ili direktno koristi item_id za dobijanje podataka
        self.tree.selection_set(item_id)
        self.show_task_details(event=None) # Pozovi originalnu metodu, koja će koristiti self.tree.selection()
    

    def edit_task(self, item, task_id):
        """Otvaranje prozora za izmenu zadatka"""
        task_values = self.tree.item(item)['values']
        description = self.tree.item(item)['tags'][2] if len(self.tree.item(item)['tags']) > 2 else ""

        edit_window = tk.Toplevel(self.root)
        edit_window.title("Izmena zadatka")
        edit_window.geometry("600x450")
        edit_window.transient(self.root)
        edit_window.grab_set()

        # Glavni okvir
        main_frame = ttk.Frame(edit_window, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Osnovni podaci
        basic_frame = ttk.LabelFrame(main_frame, text="Osnovni podaci", padding=10)
        basic_frame.pack(fill="x", pady=(0, 10))
        
        # Datum
        date_frame = ttk.Frame(basic_frame)
        date_frame.grid(row=0, column=0, sticky="w", padx=5, pady=5)
        
        ttk.Label(date_frame, text="Datum:").pack(side=tk.LEFT)
        date_entry = DateEntry(date_frame, width=12)
        date_entry.set_date(datetime.strptime(task_values[1], '%Y-%m-%d').date())
        date_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Korisnik
        user_frame = ttk.Frame(basic_frame)
        user_frame.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(user_frame, text="Korisnik:").pack(side=tk.LEFT)
        user_combo = ttk.Combobox(user_frame, width=20)
        user_combo['values'] = self.get_users()
        user_combo.set(task_values[2] or "")
        user_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Prioritet
        priority_frame = ttk.Frame(basic_frame)
        priority_frame.grid(row=0, column=2, sticky="w", padx=5, pady=5)
        
        ttk.Label(priority_frame, text="Prioritet:").pack(side=tk.LEFT)
        priority_combo = ttk.Combobox(priority_frame, width=10)
        priority_combo['values'] = ['Visok', 'Srednji', 'Nizak']
        priority_combo.set(task_values[8] or "")
        priority_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Naziv zadatka
        task_frame = ttk.Frame(basic_frame)
        task_frame.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(task_frame, text="Naziv zadatka:").pack(side=tk.LEFT)
        task_name_entry = ttk.Entry(task_frame, width=60)
        task_name_entry.insert(0, task_values[3])
        task_name_entry.pack(side=tk.LEFT, padx=(5, 0), fill="x", expand=True)
        
        # Kategorija
        category_frame = ttk.Frame(basic_frame)
        category_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=5, pady=5)
        
        ttk.Label(category_frame, text="Kategorija:").pack(side=tk.LEFT)
        category_combo = ttk.Combobox(category_frame, width=30)
        category_combo['values'] = self.get_categories()
        category_combo.set(task_values[4])
        category_combo.pack(side=tk.LEFT, padx=(5, 0))
        
        # Konfiguracija mreže
        basic_frame.columnconfigure(0, weight=1)
        basic_frame.columnconfigure(1, weight=1)
        basic_frame.columnconfigure(2, weight=1)
        
        # Okvir za vreme
        time_frame = ttk.LabelFrame(main_frame, text="Praćenje vremena", padding=10)
        time_frame.pack(fill="x", pady=(0, 10))
        
        # Početno vreme
        start_frame = ttk.Frame(time_frame)
        start_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(start_frame, text="Početak (HH:MM):").pack(side=tk.LEFT)
        start_time_entry = ttk.Entry(start_frame, width=10)
        start_time_entry.insert(0, task_values[6] or '')
        start_time_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Završno vreme
        end_frame = ttk.Frame(time_frame)
        end_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(end_frame, text="Kraj (HH:MM):").pack(side=tk.LEFT)
        end_time_entry = ttk.Entry(end_frame, width=10)
        end_time_entry.insert(0, task_values[7] or '')
        end_time_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Broj sati
        hours_frame = ttk.Frame(time_frame)
        hours_frame.pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Label(hours_frame, text="Sati:").pack(side=tk.LEFT)
        hours_entry = ttk.Entry(hours_frame, width=10)
        hours_entry.insert(0, task_values[5])
        hours_entry.pack(side=tk.LEFT, padx=(5, 0))
        
        # Opis
        desc_frame = ttk.LabelFrame(main_frame, text="Opis zadatka", padding=10)
        desc_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        desc_text = tk.Text(desc_frame, height=5, width=40)
        desc_text.insert("1.0", description)
        desc_text.pack(fill="both", expand=True)

        # Dugmad
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(0, 5))

        def save_changes():
            try:
                # Validacija obaveznih polja
                if not all([task_name_entry.get(), category_combo.get(), user_combo.get()]):
                    messagebox.showerror("Greška", "Molimo popunite sva obavezna polja")
                    return

                # Validacija sati
                try:
                    hours = float(hours_entry.get())
                    if hours <= 0:
                        raise ValueError("Sati moraju biti pozitivan broj")
                except ValueError:
                    messagebox.showerror("Greška", "Unesite ispravan broj sati")
                    return

                cursor = self.db.conn.cursor()

                # Dobijanje ID-a kategorije
                cursor.execute("SELECT id FROM categories WHERE name = ?", (category_combo.get(),))
                category_id = cursor.fetchone()[0]

                # Dobijanje ID-a korisnika
                user_name = user_combo.get()
                cursor.execute("SELECT id FROM users WHERE name = ?", (user_name,))
                user_result = cursor.fetchone()

                if not user_result:
                    # Ako korisnik ne postoji, dodajemo ga
                    cursor.execute("INSERT INTO users (name) VALUES (?)", (user_name,))
                    self.db.conn.commit()
                    user_id = cursor.lastrowid
                else:
                    user_id = user_result[0]

                # Ažuriranje zadatka
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

                # Ažuriranje izveštaja i statusne trake
                self.refresh_report()
                self.update_status_bar()

                edit_window.destroy()
                messagebox.showinfo("Uspeh", "Zadatak uspešno ažuriran!")

            except Exception as e:
                messagebox.showerror("Greška", f"Greška pri ažuriranju zadatka: {str(e)}")
                # Logovanje greške
                print(f"Error updating task: {str(e)}")

        ttk.Button(button_frame, text="Sačuvaj izmene",
                 command=save_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Otkaži",
                 command=edit_window.destroy).pack(side=tk.RIGHT, padx=5)

    def show_task_details(self, event):
        """Prikaz detalja o zadatku"""
        if event:  # Ako je pozvan iz događaja
            item = self.tree.identify_row(event.y)
            if not item:
                return
            self.tree.selection_set(item)

        # Dobijanje selektovanog reda
        selection = self.tree.selection()
        if not selection:
            return

        item = selection[0]
        task_values = self.tree.item(item)['values']

        # Provera da li je red sa ukupnim vrednostima
        if not task_values or "UKUPNO" in str(task_values):
            return

        # Kreiranje prozora za detalje
        details_window = tk.Toplevel(self.root)
        details_window.title("Detalji zadatka")
        details_window.geometry("500x400")
        details_window.transient(self.root)

        # Glavni okvir
        main_frame = ttk.Frame(details_window, padding=10)
        main_frame.pack(fill="both", expand=True)

        # Osnovni podaci
        info_frame = ttk.LabelFrame(main_frame, text="Informacije o zadatku", padding=10)
        info_frame.pack(fill="x", pady=(0, 10))

        # Kreiranje tabele sa podacima
        info_grid = ttk.Frame(info_frame)
        info_grid.pack(fill="x")

        # Red 1
        ttk.Label(info_grid, text="Datum:", font=('', 9, 'bold')).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[1]).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(info_grid, text="Korisnik:", font=('', 9, 'bold')).grid(row=0, column=2, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[2] or "").grid(row=0, column=3, sticky="w", padx=5, pady=2)

        # Red 2
        ttk.Label(info_grid, text="Zadatak:", font=('', 9, 'bold')).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[3], wraplength=350).grid(row=1, column=1, columnspan=3, sticky="w", padx=5, pady=2)

        # Red 3
        ttk.Label(info_grid, text="Kategorija:", font=('', 9, 'bold')).grid(row=2, column=0, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[4]).grid(row=2, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(info_grid, text="Prioritet:", font=('', 9, 'bold')).grid(row=2, column=2, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[8] or "").grid(row=2, column=3, sticky="w", padx=5, pady=2)

        # Red 4
        ttk.Label(info_grid, text="Vreme:", font=('', 9, 'bold')).grid(row=3, column=0, sticky="w", padx=5, pady=2)
        time_text = f"{task_values[6] or ''} - {task_values[7] or ''}"
        ttk.Label(info_grid, text=time_text).grid(row=3, column=1, sticky="w", padx=5, pady=2)

        ttk.Label(info_grid, text="Sati:", font=('', 9, 'bold')).grid(row=3, column=2, sticky="w", padx=5, pady=2)
        ttk.Label(info_grid, text=task_values[5]).grid(row=3, column=3, sticky="w", padx=5, pady=2)

        # Opis
        desc_frame = ttk.LabelFrame(main_frame, text="Opis", padding=10)
        desc_frame.pack(fill="both", expand=True)

        desc_text = tk.Text(desc_frame, wrap=tk.WORD, padx=10, pady=10)
        desc_text.insert("1.0", self.tree.item(item)['tags'][2] if len(self.tree.item(item)['tags']) > 2 else "Nema opisa")
        desc_text.config(state="disabled")

        # Dodavanje klizača
        scrollbar = ttk.Scrollbar(desc_frame, orient="vertical", command=desc_text.yview)
        desc_text.configure(yscrollcommand=scrollbar.set)

        desc_text.pack(side=tk.LEFT, fill="both", expand=True)
        scrollbar.pack(side=tk.RIGHT, fill="y")

        # Dugmad
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))

        # Dobijanje ID-a zadatka
        task_id = self.tree.item(item)['tags'][1] if len(self.tree.item(item)['tags']) > 1 else None

        if task_id and str(task_id.isdigit()):
            ttk.Button(button_frame, text="Izmeni",
                     command=lambda: [details_window.destroy(), self.edit_task(item, task_id)]).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Obriši",
                     command=lambda: [details_window.destroy(), self.delete_task(task_id)]).pack(side=tk.LEFT, padx=5)

        ttk.Button(button_frame, text="Zatvori",
                 command=details_window.destroy).pack(side=tk.RIGHT, padx=5)

    def show_statistics(self):
        """Prikaz statistike za izabrani period"""
        # Čišćenje postojećih podataka
        for item in self.cat_tree.get_children():
            self.cat_tree.delete(item)
        for item in self.user_tree.get_children():
            self.user_tree.delete(item)

        # Dobijanje vrednosti filtera
        date_from = self.stats_date_from.get_date()
        date_to = self.stats_date_to.get_date()

        # Statistika po kategorijama
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

        # Izračunavanje ukupnih sati
        total_hours = sum(row[1] for row in category_stats)

        # Popunjavanje tabele kategorija
        for i, (category, hours) in enumerate(category_stats):
            percentage = (hours / total_hours * 100) if total_hours > 0 else 0
            self.cat_tree.insert("", tk.END, values=(category, f"{hours:.2f}", f"{percentage:.1f}%"),
                               tags=('oddrow' if i % 2 else 'evenrow'))

        # Dodavanje ukupno
        self.cat_tree.insert("", tk.END, values=("UKUPNO", f"{total_hours:.2f}", "100.0%"),
                           tags=('total',))

        # Statistika po korisnicima
        cursor.execute("""
            SELECT users.name, SUM(tasks.hours_spent) as total_hours
            FROM tasks
            LEFT JOIN users ON tasks.user_id = users.id
            WHERE tasks.date BETWEEN ? AND ?
            GROUP BY users.name
            ORDER BY total_hours DESC
        """, (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

        user_stats = cursor.fetchall()

        # Popunjavanje tabele korisnika
        for i, (user, hours) in enumerate(user_stats):
            percentage = (hours / total_hours * 100) if total_hours > 0 else 0
            self.user_tree.insert("", tk.END, values=(user or "Nepoznat", f"{hours:.2f}", f"{percentage:.1f}%"),
                                tags=('oddrow' if i % 2 else 'evenrow'))

        # Dodavanje ukupno
        self.user_tree.insert("", tk.END, values=("UKUPNO", f"{total_hours:.2f}", "100.0%"),
                            tags=('total',))

    def export_to_excel(self):
        """Izvoz izvestaja (tab Reports) u Excel."""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel fajlovi", "*.xlsx"), ("Svi fajlovi", "*.*")]
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
                messagebox.showinfo("Info", "Nema podataka za izvoz.")
                return

            export.write_task_report(file_path, data)
            messagebox.showinfo("Uspeh", "Izvestaj uspesno izvezen!")

        except Exception as e:
            messagebox.showerror("Greska", f"Greska pri izvozu u Excel: {str(e)}")
            print(f"Error exporting to Excel: {str(e)}")

    def export_statistics(self):
        """Izvoz statistike (tab Stats) u Excel."""
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx",
                filetypes=[("Excel fajlovi", "*.xlsx"), ("Svi fajlovi", "*.*")]
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
            messagebox.showinfo("Uspeh", "Statistika uspesno izvezena!")

        except Exception as e:
            messagebox.showerror("Greska", f"Greska pri izvozu statistike: {str(e)}")
            print(f"Error exporting statistics: {str(e)}")

    def refresh_future_tasks(self):
        """Osvežavanje liste budućih zadataka"""
        try:
            # Čišćenje tabele
            for item in self.future_tree.get_children():
                self.future_tree.delete(item)

            # Dobijanje vrednosti filtera
            date_from_obj = self.future_date_from.get_date()
            date_to_obj = self.future_date_to.get_date()
            user_filter_val = self.future_user_filter.get()
            category_filter_val = self.future_category_filter.get()

            query = """
                SELECT ft.id, ft.date, u.name, ft.task_name, c.name, ft.priority,
                    CASE ft.completed WHEN 1 THEN 'Završen' ELSE 'Aktivan' END as status,
                    ft.description
                FROM future_tasks ft
                LEFT JOIN users u ON ft.user_id = u.id
                LEFT JOIN categories c ON ft.category_id = c.id
                WHERE ft.date BETWEEN ? AND ?
            """
            params = [date_from_obj.strftime('%Y-%m-%d'), date_to_obj.strftime('%Y-%m-%d')]

            if user_filter_val != 'Svi':
                query += " AND u.name = ?"
                params.append(user_filter_val)
            if category_filter_val != 'Sve':
                query += " AND c.name = ?"
                params.append(category_filter_val)

            query += " ORDER BY ft.date ASC, ft.priority DESC" # Možda drugačije sortiranje?

            cursor = self.db.conn.cursor()
            cursor.execute(query, params)
            fetched_rows = cursor.fetchall()

            row_color_index = 0
            task_display_count = 0
            for row_data in fetched_rows:
                task_display_count += 1
                future_task_id_db = row_data[0]
                # Vrednosti za prikaz: #, Datum, Korisnik, Zadatak, Kategorija, Prioritet, Status
                # row_data[0] je ID, row_data[1] je Datum, ..., row_data[6] je Status
                # row_data[7] je opis, koji ne prikazujemo direktno u koloni ali treba za tag
                display_values = [task_display_count] + list(row_data[1:7])

                tag_for_row_color = 'evenrow' if row_color_index % 2 == 0 else 'oddrow'
                description_val = row_data[7] if len(row_data) > 7 and row_data[7] is not None else ""

                # ISPRAVNO TAGOVANJE: (boja, ID_zadatka_kao_string, opis)
                item_tags = (tag_for_row_color, str(future_task_id_db), description_val)

                self.future_tree.insert("", "end", values=display_values, tags=item_tags)
                row_color_index += 1

        except Exception as e:
            messagebox.showerror("Greška", f"Greška pri osvežavanju budućih zadataka: {str(e)}")
            print(f"Error refreshing future tasks: {str(e)}")

    def get_all_users(self):
        """Vraća listu svih korisnika"""
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT name FROM users ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

    def get_all_categories(self):
            """Vraća listu svih kategorija"""
            cursor = self.db.conn.cursor()
            cursor.execute("SELECT name FROM categories ORDER BY name")
            return [row[0] for row in cursor.fetchall()]
    
    # ... unutar klase TimeTracker ...

    def show_future_task_details(self, event): # event može biti None
        """Prikaz detalja o budućem zadatku u novom prozoru"""
        item_id_tk = None
        if event is not None: # Pozvano dvoklikom
            selected_item_tuple = self.future_tree.selection()
            if not selected_item_tuple: return
            item_id_tk = selected_item_tuple[0]
        else: # Pozvano iz kontekstnog menija
            selected_item_tuple = self.future_tree.selection()
            if not selected_item_tuple: return
            item_id_tk = selected_item_tuple[0]

        if not item_id_tk: return

        item_data = self.future_tree.item(item_id_tk)
        tags = item_data.get('tags', [])

        # KORIGOVANA LINIJA: Konvertujemo tags[1] u string pre poziva .isdigit()
        if not (tags and len(tags) > 1 and tags[1] is not None and str(tags[1]).isdigit()):
            # print(f"Debug show_future_task_details: Nije red sa zadatkom ili nema validan ID. Tags: {tags}")
            return

        future_task_id_for_db = int(str(tags[1])) # Konvertuj u int za upit

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
                messagebox.showerror("Greška", "Detalji budućeg zadatka nisu pronađeni.")
                return

            details_window = tk.Toplevel(self.root)
            details_window.title("Detalji budućeg zadatka")
            details_window.geometry("500x400") # Malo manje visine, nema sati/vremena
            details_window.transient(self.root)
            details_window.grab_set()

            main_frame = ttk.Frame(details_window, padding=15)
            main_frame.pack(fill="both", expand=True)

            fields = [
                ("Datum:", task[0]),
                ("Korisnik:", task[1] if task[1] else "N/A"),
                ("Zadatak:", task[2]),
                ("Kategorija:", task[3] if task[3] else "N/A"),
                ("Prioritet:", task[4] if task[4] else "N/A"),
                ("Status:", "Završen" if task[6] == 1 else "Aktivan (planiran)")
            ]

            for i, (label_text, value_text) in enumerate(fields):
                ttk.Label(main_frame, text=label_text, font=('TkDefaultFont', 10, 'bold')).grid(row=i, column=0, sticky="ne", pady=3, padx=5)
                if label_text == "Zadatak:":
                    task_name_label = ttk.Label(main_frame, text=value_text if value_text else "N/A", wraplength=300, justify=tk.LEFT)
                    task_name_label.grid(row=i, column=1, sticky="nw", pady=3, padx=5)
                else:
                    ttk.Label(main_frame, text=value_text if value_text else "N/A").grid(row=i, column=1, sticky="nw", pady=3, padx=5)


            ttk.Label(main_frame, text="Opis:", font=('TkDefaultFont', 10, 'bold')).grid(row=len(fields), column=0, sticky="ne", pady=(10,3), padx=5)
            desc_frame = ttk.Frame(main_frame)
            desc_frame.grid(row=len(fields) + 1, column=0, columnspan=2, sticky="nsew", pady=2, padx=5)
            desc_frame.grid_columnconfigure(0, weight=1)
            desc_frame.grid_rowconfigure(0, weight=1)

            desc_text_widget = tk.Text(desc_frame, height=5, width=50, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1)
            desc_text_widget.insert(tk.END, task[5] if task[5] else "Nema opisa.")
            desc_text_widget.config(state=tk.DISABLED)
            desc_text_widget.pack(side=tk.LEFT, fill="both", expand=True, pady=2, padx=2)

            desc_scrollbar = ttk.Scrollbar(desc_frame, orient="vertical", command=desc_text_widget.yview)
            desc_scrollbar.pack(side=tk.RIGHT, fill="y")
            desc_text_widget.config(yscrollcommand=desc_scrollbar.set)
            main_frame.grid_rowconfigure(len(fields) + 1, weight=1)


            button_frame = ttk.Frame(main_frame)
            button_frame.grid(row=len(fields) + 2, column=0, columnspan=2, pady=(15,5))

            ttk.Button(button_frame, text="Prebaci za unos",
                    command=lambda: (self.prepare_future_task_for_entry(str(future_task_id_for_db)), details_window.destroy())).pack(side=tk.LEFT, padx=5)
            if task[6] == 0: # Ako nije završen (completed == 0)
                ttk.Button(button_frame, text="Označi kao završen",
                        command=lambda: (self.mark_future_task_completed(str(future_task_id_for_db)), details_window.destroy())).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Obriši",
                    command=lambda: (self.delete_future_task(str(future_task_id_for_db)), details_window.destroy())).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text="Zatvori", command=details_window.destroy).pack(side=tk.LEFT, padx=5)

        except Exception as e:
            messagebox.showerror("Greška", f"Greška pri prikazivanju detalja budućeg zadatka: {str(e)}")
            print(f"Error showing future task details: {str(e)}")

    def show_future_task_context_menu(self, event):
        """Prikaz kontekstnog menija za buduće zadatke"""
        item_id = self.future_tree.identify_row(event.y)
        if not item_id:
            return

        item_data = self.future_tree.item(item_id)
        tags = item_data.get('tags', []) # tags bi trebalo da budu (boja, future_task_id_str, opis)

        # KORIGOVANA LINIJA: Konvertujemo tags[1] u string pre poziva .isdigit()
        if tags and len(tags) > 1 and tags[1] is not None and str(tags[1]).isdigit():
            self.future_tree.selection_set(item_id)
            future_task_id_str = str(tags[1]) # Osiguravamo da je future_task_id_str string

            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Prikaži detalje",
                        command=lambda item=item_id: self.show_future_task_details_from_item(item))
            menu.add_command(label="Prebaci za unos (kao aktivni)",
                        command=lambda ftid=future_task_id_str: self.prepare_future_task_for_entry(ftid))
            menu.add_separator()
            menu.add_command(label="Označi kao završen (i ukloni)",
                        command=lambda ftid=future_task_id_str: self.mark_future_task_completed(ftid))
            menu.add_command(label="Obriši budući zadatak",
                        command=lambda ftid=future_task_id_str: self.delete_future_task(ftid))
            menu.post(event.x_root, event.y_root)
        # else:
            # print(f"Debug show_future_task_context_menu: Nije red sa zadatkom ili nema validan ID. Tags: {tags}")

    def show_future_task_details_from_item(self, item_id):
        if not item_id:
            return
        self.future_tree.selection_set(item_id) # Postavi selekciju
        self.show_future_task_details(event=None) # Pozovi originalnu metodu
        

    def mark_future_task_completed(self, future_task_id_str):
        """Obeležava budući zadatak kao završen (briše ga iz liste)."""
        if not messagebox.askyesno("Potvrda", "Da li ste sigurni da želite da označite ovaj zadatak kao završen i uklonite ga sa liste budućih zadataka?"):
            return
        try:
            future_task_id = int(future_task_id_str)
            cursor = self.db.conn.cursor()
            cursor.execute("DELETE FROM future_tasks WHERE id = ?", (future_task_id,))
            self.db.conn.commit()
            messagebox.showinfo("Uspeh", "Budući zadatak je označen kao završen i uklonjen.")
            self.refresh_future_tasks()
        except ValueError:
            messagebox.showerror("Greška", "Nevažeći ID zadatka.")
        except Exception as e:
            messagebox.showerror("Greška", f"Greška pri označavanju zadatka kao završenog: {str(e)}")

    def delete_future_task(self, task_id=None):
        """Brisanje budućeg zadatka"""
        if not task_id:
            selection = self.future_tree.selection()
            if not selection:
                messagebox.showinfo("Informacija", "Molimo izaberite zadatak")
                return

            item = selection[0]
            task_id = self.future_tree.item(item)['tags'][0]

        # Potvrda brisanja
        if not messagebox.askyesno("Potvrda", "Da li ste sigurni da želite da obrišete ovaj zadatak?"):
            return

        # Brisanje zadatka
        cursor = self.db.conn.cursor()
        cursor.execute("DELETE FROM future_tasks WHERE id = ?", (task_id,))
        self.db.conn.commit()

        # Osvežavanje liste
        self.refresh_future_tasks()
        messagebox.showinfo("Uspeh", "Zadatak je uspešno obrisan")
        pass  # Dodajte kod iz prethodnog odgovora
    

    def run(self):
        """Pokretanje glavne petlje aplikacije."""
        try:
            today = datetime.now().date()
            self.date_from.set_date(today - timedelta(days=2))
            self.date_to.set_date(today)

            self.refresh_future_tasks()
            self.root.mainloop()
        except Exception as e:
            messagebox.showerror("Kritična greška", f"Došlo je do kritične greške: {str(e)}")
