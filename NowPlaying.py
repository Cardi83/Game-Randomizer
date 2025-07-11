"""
🎮 Now Playing... Game Randomizer (Built with NiceGUI & SQLite)

This is a lightweight browser-based game selector that allows users to:
- Add individual or bulk game titles (via CSV)
- Search, filter, and delete games from a local database
- Select multiple games and bulk-delete
- Randomly pick a game from the list
- Maintain all game data in a persistent SQLite database

Key Features:
- Clean, responsive UI built with NiceGUI
- All database interactions use parameterized queries for safety
- Includes protections for duplicate entries and handles CSV uploads gracefully
- Supports UI interaction optimizations (scrolling, animations, hover highlights)

Security Notes:
- Inputs are trimmed and parameterized to prevent SQL injection
"""

from nicegui import ui, events
import csv
import html
import random
import re
import sqlite3

# -=-=-=-=-=- DATABASE SETUP & CONFIG -=-=-=-=-=-=-
conn = sqlite3.connect('quick_games.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )
''')
conn.commit()

# -=-=-=-=-=- GLOBAL -=-=-=-=-=-=-
selected_game = None
checkbox_states = {}  # Keeps game_name: bool for each checkbox

# -=-=-=-=-=- FUNCTIONS -=-=-=-=-=-=-

def get_all_games():
    cursor.execute('SELECT name FROM games ORDER BY name')
    return [row[0] for row in cursor.fetchall()]

def search_games(term):
    term = term.strip()
    if not term:
        return []
    term_lower = term.lower()
    all_titles = get_all_games()
    exact_matches = [title for title in all_titles if title.lower() == term_lower]
    word_start_pattern = re.compile(rf'\b{re.escape(term_lower)}', re.IGNORECASE)
    partial_matches = [
        title for title in all_titles
        if word_start_pattern.search(title.lower()) and title.lower() != term_lower
    ]
    return exact_matches + partial_matches

def update_search_results():
    global search_input, search_results
    term = (search_input.value or '').strip()
    search_results.clear()
    if not term:
        return
    results = search_games(term)
    if results:
        for game in results:
            with search_results:
                with ui.row().classes('items-center').style('justify-content: space-between;'):
                    ui.label(game).classes('text-sm').style('font-size: 12px; white-space: nowrap;')
    else:
        with search_results:
            ui.label('No matches found.').classes('text-sm text-gray')

def clear_search():
    global selected_game, search_input, search_results
    selected_game = None
    search_input.value = ''
    search_results.clear()
    refresh_all_games()

def handle_csv_upload(e: events.UploadEventArguments):
    file = e.content.read().decode('utf-8').splitlines()
    reader = csv.reader(file)
    imported = 0
    skipped = 0
    for row in reader:
        if row:
            game = row[0].strip()
            if game:
                try:
                    cursor.execute('INSERT INTO games (name) VALUES (?)', (game,))
                    imported += 1
                except sqlite3.IntegrityError:
                    skipped += 1
    conn.commit()
    ui.notify(f"Imported: {imported}, Skipped: {skipped} (duplicates)", type='positive')
    refresh_all_games()

def confirm_bulk_deletion():
    selected_games = [game for game, checked in checkbox_states.items() if checked]
    if not selected_games:
        ui.notify("No games selected for deletion.", type='warning')
        return

    dialog = ui.dialog()

    def do_delete():
        for game in selected_games:
            cursor.execute('DELETE FROM games WHERE name = ?', (game,))
            checkbox_states.pop(game, None)
        conn.commit()
        refresh_all_games()
        ui.notify(f"✅ Deleted {len(selected_games)} game(s).", type='positive')
        dialog.close()
    # Generate confirmation message
    if len(selected_games) == 1:
        sname = html.escape(selected_games[0])
        message = f"Delete '<strong>{sname}</strong>'?"
    else:
        message = f"Delete {len(selected_games)} selected games?"

    with dialog, ui.card():
        ui.html(message)
        with ui.row():
            ui.button("Yes", on_click=do_delete)
            ui.button("Cancel", on_click=dialog.close)
    dialog.open()

def add_game(game):
    global game_input, add_result
    game = game.strip()
    if not game:
        add_result.text = "❗ Enter a game title."
        add_result.classes('opacity-100').style('font-size: 15px;')
        ui.timer(3.0, lambda: (add_result.classes('opacity-0'), add_result.set_text('')), once=True)
        return
    try:
        cursor.execute('INSERT INTO games (name) VALUES (?)', (game,))
        conn.commit()
        add_result.text = f"✅  Added: {game}"
        add_result.classes('opacity-100').style('font-size: 15px; color: green;')
        ui.timer(3.0, lambda: (add_result.classes('opacity-0'), add_result.set_text('')), once=True)
        game_input.value = ''
        update_search_results()
        refresh_all_games()
    except sqlite3.IntegrityError:
        add_result.text = f"⚠️  {game} is already in the list."
        add_result.classes('opacity-100').style('font-size: 15px;')
        ui.timer(3.0, lambda: (add_result.classes('opacity-0'), add_result.set_text('')), once=True)

def pick_random():
    global random_result
    games = get_all_games()
    random_result.clear()
    if games:
        choice = random.choice(games)
        with random_result:
            with ui.row().style(
                "border: 2px solid #78b3f0; border-radius: 6px; padding: 4px 8px; margin-top: 1px; min-height: 33px;"
            ).classes('gap-1 items-center'):
                ui.label("🕹️").style("line-height: 1;")
                ui.label(choice).style(
                    "font-weight: bold; font-size: 14px; line-height: 1.3; "
                    "max-width: 252px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;"
                )
    else:
        with random_result:
            ui.label("❗ No games in the database.")

def create_checkbox(game_name):
    if game_name not in checkbox_states:
        checkbox_states[game_name] = False
        
    def on_change_handler(e):
        checkbox_states[game_name] = e.value

    checkbox = ui.checkbox().bind_value(checkbox_states, game_name).props('dense').style(
        'transform: scale(0.8); padding: 0; margin: -3px;'
    )
    checkbox.on('change', on_change_handler)
    return checkbox

def refresh_all_games():
    global all_games_column, games_label
    all_games_column.clear()
    all_games = get_all_games()
    games_label.text = f'💿\u00A0\u00A0All Games ({len(all_games)})'
    if all_games:
        all_games.sort(key=lambda g: g.lower())
        for game in all_games:
            with all_games_column:
                row_id = f'game-{game.replace(" ", "_")}'
                with ui.row().classes('items-center').style('margin-left: -5px; gap: 4px; margin-bottom: -4px;').props(f'id={row_id}'):
                    create_checkbox(game)
                    ui.label(game).classes('text-sm').style(
                        'line-height: 1.2; font-size: 14px; width: 310px; word-wrap: break-word; white-space: normal;'
                        )
    else:
        with all_games_column:
            ui.label('No games found.').classes('text-sm text-gray')

def select_all_games():
    for game in get_all_games():
        checkbox_states[game] = True
    refresh_all_games()

def clear_selected_games():
    for game in get_all_games():
        checkbox_states[game] = False
    refresh_all_games()

def scroll_to_game(game_name):
    scroll_id = f'game-{game_name.replace(" ", "_")}'
    ui.run_javascript(f'''
        const el = document.getElementById("{scroll_id}");
        if (el) el.scrollIntoView({{ behavior: "smooth", block: "center" }});
    ''')

def handle_input():
    global selected_game, search_input, search_results
    term = (search_input.value or '').strip()
    search_results.clear()
    if not term:
        selected_game = None
        refresh_all_games()
        return
    matches = search_games(term)
    if not matches:
        with search_results:
            ui.label('No matches found.').classes('text-sm text-gray')
        return
    if len(matches) == 1:
        selected_game = matches[0]
        refresh_all_games()
        scroll_id = f'game-{selected_game.replace(" ", "_")}'
        ui.run_javascript(f'''
            const el = document.getElementById("{scroll_id}");
            if (el) el.scrollIntoView({{ behavior: "smooth", block: "center" }});
        ''')
    else:
        selected_game = None
        refresh_all_games()
    for game in matches:
        with search_results:
            ui.label(game)\
            .classes('text-sm cursor-pointer text-blue hover-highlight')\
            .style('font-size: 12px; white-space: nowrap;')\
            .on('click', lambda g=game: scroll_to_game(g))


# -=-=-=-=-=- MAIN UI -=-=-=-=-=-=-
@ui.page('/')
def main():
    global game_input, add_result, search_input, search_results
    global games_label, all_games_column, random_result

    ui.add_head_html('''
    <link href="https://fonts.googleapis.com/css2?family=Lato&display=swap" rel="stylesheet">
    <style>
        * {
            font-family: 'Lato', sans-serif;
        }
        .q-btn .q-focus-helper {
            display: none !important;
        }
        .hover-highlight {
            transition: background-color 0.2s ease;
            padding: 2px 6px;
            border-radius: 4px;
        }
        .hover-highlight:hover {
            background-color: #e3f2fd;
        }
    </style>
    ''')

    ui.label('🎮 Now Playing...')\
        .style('font-size: 25px; font-weight: bold; margin-top: 2px; margin-bottom: -10px;')
    # --- Fixed position
    with ui.column().style('width: 850px; margin: 0 auto; margin-left: 0;'):
        # --- Game Randomizer Section
        with ui.row().style('align-items: center; gap: 12px; margin-bottom: -3px; margin-left: 270px;'):
            ui.button('ROLL\u00A0\u00A0\u00A0🎲', on_click=pick_random).props('color=blue-4')\
                .style('border-radius: 6px; padding: 6px 12px;')
            random_result = ui.column()\
                .style('height: 38px; justify-content: center; align-items: center;')\
                .classes('items-center')

        with ui.row().style('align-items: flex-start; gap: 20px;'):
            with ui.column().style('gap: 4px; min-width: 300px; max-height: 360px; overflow-y: auto;'):
                ui.label('Enter Game Title').style('font-weight: bold; font-size: 14px;')
                with ui.row().style('gap: 8px; align-items: center; margin-top: -4px;'):
                    game_input = ui.input(placeholder='e.g., Resident Evil').props('outlined dense clearable').style('width: 170px;')
                    game_input.on('keydown.enter', lambda: add_game(game_input.value))
                    ui.upload(on_upload=handle_csv_upload, auto_upload=True, label='').style('display: none')
                    ui.button(
                        icon='upload_file',
                        on_click=lambda: ui.run_javascript("document.querySelector('input[type=file]').click()")
                    ).props('dense flat color=blue-4').style('font-size: 22px; margin-left: -11px;')

                with ui.row().style('gap: 8px;'):
                    ui.button('Add Game', on_click=lambda: add_game(game_input.value)).props('color=green')\
                        .style('border-radius: 6px; padding: 6px 12px;')
                add_result = ui.label().classes('transition-opacity duration-5000 ease-linear opacity-0')\
                    .style('min-height: 30px; display: block; margin-top: 6px; max-width: 260px; white-space: normal; overflow-wrap: break-word;')


                ui.label('🔍 Search').style('margin-top: 40px; font-weight: bold;')
                search_input = ui.input(placeholder='Type in a game name...').props('lined dense clearable').style('width: 170px; margin-top: -10px;')
                search_input.on('keydown.enter', lambda _: handle_input())
                search_input.on('clear', lambda _: clear_search())
                search_input.on('keydown.backspace', lambda _: clear_search())  

                with ui.element().style(
                    'margin-top: 10px; width: 260px; height: 200px; overflow-y: auto; overflow-x: auto; '
                    'border-radius: 6px; padding: 6px;'
                ):
                    search_results = ui.column().style('min-width: 260px; gap: 6px;')
            # --- Vertical Separator
            ui.separator().props('vertical').style('height: 285px; margin-left: -80px; margin-right: 10px;')

            with ui.column().style('gap: 6px; min-width: 300px;'):
                games_label = ui.label().style('font-weight: bold;')
                # Set fixed width and height for the games column
                all_games_column = ui.column().style('height: 250px; width: 380px; overflow-y: auto; border: 1px solid #ccc; padding: 10px;')

                with ui.row().style('gap: 8px; margin-top: 6px;'):
                    ui.button('Select All', on_click=select_all_games).props('color=blue-4')\
                        .style('border-radius: 6px; padding: 6px 12px;')
                    ui.button('CLEAR', on_click=clear_selected_games).props('color=blue-4')\
                        .style('border-radius: 6px; padding: 6px 12px;')
                    ui.button('Delete', on_click=confirm_bulk_deletion).props('color=red')\
                        .style('border-radius: 6px; padding: 6px 12px; margin-left: 123px;')


    refresh_all_games()
    random_result.clear()

ui.run(title='Now Playing... Game Randomizer', reload=True)