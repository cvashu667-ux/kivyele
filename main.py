import sqlite3
from kivy.app import App
from kivy.lang import Builder
from kivy.uix.screenmanager import Screen
from kivy.properties import ObjectProperty, StringProperty


KV_FILE = "main.kv"


def ensure_db(conn, cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        votes INTEGER DEFAULT 0
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS voters (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        password TEXT NOT NULL,
        voted INTEGER DEFAULT 0
    )
    """)
    conn.commit()


class HomeScreen(Screen):
    pass


class AdminLoginScreen(Screen):
    password_input = ObjectProperty()

    def do_login(self):
        app = App.get_running_app()
        pwd = self.password_input.text
        if pwd == app.admin_password:
            app.root.current = 'admin_panel'
            self.password_input.text = ''
        else:
            app.show_message('admin_login_msg', 'Incorrect password')


class AdminPanelScreen(Screen):
    candidate_input = ObjectProperty()
    admin_msg = ObjectProperty()

    def add_candidate(self):
        name = self.candidate_input.text.strip()
        if not name:
            App.get_running_app().show_message('admin_panel_msg', 'Enter candidate name')
            return
        app = App.get_running_app()
        try:
            app.cursor.execute("INSERT INTO candidates (name) VALUES (?)", (name,))
            app.conn.commit()
            app.show_message('admin_panel_msg', f"Candidate '{name}' added")
            self.candidate_input.text = ''
        except sqlite3.IntegrityError:
            app.show_message('admin_panel_msg', 'Candidate already exists')

    def remove_candidate(self):
        name = self.candidate_input.text.strip()
        if not name:
            App.get_running_app().show_message('admin_panel_msg', 'Enter candidate name')
            return
        app = App.get_running_app()
        app.cursor.execute("DELETE FROM candidates WHERE name = ?", (name,))
        app.conn.commit()
        app.show_message('admin_panel_msg', f"Candidate '{name}' removed")
        self.candidate_input.text = ''

    def refresh_voters(self):
        app = App.get_running_app()
        app.cursor.execute("SELECT id, name, voted FROM voters")
        rows = app.cursor.fetchall()
        text = '\n'.join([f"ID: {r[0]}, Name: {r[1]}, Voted: {'Yes' if r[2] else 'No'}" for r in rows])
        app.set_text('voters_list', text or 'No voters')

    def refresh_results(self):
        app = App.get_running_app()
        app.cursor.execute("SELECT name, votes FROM candidates")
        rows = app.cursor.fetchall()
        text = '\n'.join([f"{r[0]}: {r[1]} votes" for r in rows])
        app.set_text('results_list', text or 'No results')


class RegisterScreen(Screen):
    voter_id = ObjectProperty()
    voter_name = ObjectProperty()
    voter_pass = ObjectProperty()

    def do_register(self):
        app = App.get_running_app()
        vid = self.voter_id.text.strip()
        name = self.voter_name.text.strip()
        pwd = self.voter_pass.text
        if not vid or not name or not pwd:
            app.show_message('register_msg', 'Fill all fields')
            return
        app.cursor.execute("SELECT * FROM voters WHERE id = ?", (vid,))
        if app.cursor.fetchone():
            app.show_message('register_msg', 'Voter ID already exists')
            return
        app.cursor.execute("INSERT INTO voters (id, name, password) VALUES (?, ?, ?)", (vid, name, pwd))
        app.conn.commit()
        app.show_message('register_msg', f"Voter '{name}' registered")
        self.voter_id.text = self.voter_name.text = self.voter_pass.text = ''


class VoterLoginScreen(Screen):
    voter_id = ObjectProperty()
    voter_pass = ObjectProperty()

    def do_login(self):
        app = App.get_running_app()
        vid = self.voter_id.text.strip()
        pwd = self.voter_pass.text
        if not vid or not pwd:
            app.show_message('voter_login_msg', 'Enter credentials')
            return
        app.cursor.execute("SELECT voted FROM voters WHERE id = ? AND password = ?", (vid, pwd))
        row = app.cursor.fetchone()
        if not row:
            app.show_message('voter_login_msg', 'Invalid credentials')
            return
        if row[0]:
            app.show_message('voter_login_msg', 'You have already voted')
            return
        app.current_voter = vid
        app.root.current = 'vote'
        self.voter_id.text = self.voter_pass.text = ''


class VoteScreen(Screen):
    candidates_box = ObjectProperty()

    def on_enter(self):
        self.refresh_candidates()

    def refresh_candidates(self):
        app = App.get_running_app()
        container = self.ids.candidates_box
        container.clear_widgets()
        app.cursor.execute("SELECT id, name FROM candidates")
        rows = app.cursor.fetchall()
        if not rows:
            from kivy.uix.label import Label
            container.add_widget(Label(text='No candidates'))
            return
        from kivy.uix.button import Button
        for cid, name in rows:
            btn = Button(text=name, size_hint_y=None, height='40dp')
            btn.bind(on_release=lambda b, cid=cid: App.get_running_app().cast_vote(cid))
            container.add_widget(btn)


class ResultsScreen(Screen):
    pass


class ElectionApp(App):
    admin_password = StringProperty('admin123')
    conn = None
    cursor = None
    current_voter = None

    def build(self):
        try:
            root = Builder.load_file(KV_FILE)
        except Exception as e:
            raise
        self.conn = sqlite3.connect('election.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        ensure_db(self.conn, self.cursor)
        return root

    def show_message(self, widget_id, message):
        # Search all screens for the widget id and set its text
        try:
            for screen in getattr(self.root, 'screens', []):
                w = screen.ids.get(widget_id)
                if w:
                    w.text = message
                    return
        except Exception:
            pass

    def set_text(self, widget_id, text):
        try:
            for screen in getattr(self.root, 'screens', []):
                w = screen.ids.get(widget_id)
                if w:
                    w.text = text
                    return
        except Exception:
            pass

    def cast_vote(self, candidate_id):
        if not self.current_voter:
            return
        self.cursor.execute("UPDATE candidates SET votes = votes + 1 WHERE id = ?", (candidate_id,))
        self.cursor.execute("UPDATE voters SET voted = 1 WHERE id = ?", (self.current_voter,))
        self.conn.commit()
        self.current_voter = None
        self.show_message('vote_msg', 'Vote cast successfully')
        self.root.current = 'home'


if __name__ == '__main__':
    ElectionApp().run()
