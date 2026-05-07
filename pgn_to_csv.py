"""
pgn_to_csv.py — Convert a PGN chess game file to CSV for analysis in R.

Usage:
    python pgn_to_csv.py input.txt output.csv

Each row = one game.
Columns: Event, GameNo, White, Black, WhiteElo, BlackElo, WhiteRD, BlackRD,
         TimeControl, Date, Time, ECO, PlyCount, Result, Moves (all moves joined),
         Move_1 … Move_N (individual half-moves / plies)
"""

import re
import csv
import sys
from pathlib import Path


# ── helpers ──────────────────────────────────────────────────────────────────

HEADER_RE = re.compile(r'\[(\w+)\s+"([^"]*)"\]')

# Strip move numbers, annotation symbols, and comments { … } from the move text
MOVE_NUM_RE  = re.compile(r'\d+\.+')
COMMENT_RE   = re.compile(r'\{[^}]*\}')
RESULT_TAIL  = re.compile(r'(1-0|0-1|1/2-1/2|\*)$')
ANNOTATION_RE = re.compile(r'[!?]+')


def clean_moves(move_text: str) -> list[str]:
    """Return a list of individual SAN half-moves (plies), no move numbers."""
    text = COMMENT_RE.sub('', move_text)          # remove { comments }
    text = RESULT_TAIL.sub('', text).strip()       # remove trailing result
    text = MOVE_NUM_RE.sub('', text)               # remove 1. 2. 3... etc.
    text = ANNOTATION_RE.sub('', text)             # remove ! ? !! ?? !? ?!
    moves = text.split()
    return moves


def parse_pgn(path: Path) -> list[dict]:
    games = []
    current_headers: dict[str, str] = {}
    move_lines: list[str] = []
    in_moves = False

    with open(path, encoding='utf-8', errors='replace') as fh:
        for raw_line in fh:
            line = raw_line.strip()

            if line.startswith('['):
                # If we were collecting moves, a new header block ends the game
                if in_moves and current_headers:
                    games.append(_build_game(current_headers, move_lines))
                    current_headers = {}
                    move_lines = []
                    in_moves = False

                m = HEADER_RE.match(line)
                if m:
                    current_headers[m.group(1)] = m.group(2)

            elif line == '':
                # Blank line between headers and move text — start collecting moves
                if current_headers and not in_moves:
                    in_moves = True
            else:
                if in_moves:
                    move_lines.append(line)

    # Don't forget the last game
    if current_headers and move_lines:
        games.append(_build_game(current_headers, move_lines))

    return games


def _build_game(headers: dict, move_lines: list[str]) -> dict:
    move_text = ' '.join(move_lines)
    moves = clean_moves(move_text)

    row = {
        'Event':       headers.get('Event', ''),
        'GameNo':      headers.get('FICSGamesDBGameNo', ''),
        'White':       headers.get('White', ''),
        'Black':       headers.get('Black', ''),
        'WhiteElo':    headers.get('WhiteElo', ''),
        'BlackElo':    headers.get('BlackElo', ''),
        'WhiteRD':     headers.get('WhiteRD', ''),
        'BlackRD':     headers.get('BlackRD', ''),
        'TimeControl': headers.get('TimeControl', ''),
        'Date':        headers.get('Date', ''),
        'Time':        headers.get('Time', ''),
        'ECO':         headers.get('ECO', ''),
        'PlyCount':    headers.get('PlyCount', ''),
        'Result':      headers.get('Result', ''),
        'Moves':       ' '.join(moves),
    }

    # Separate columns for White and Black moves: White_Move_1, Black_Move_1, …
    white_moves = moves[0::2]  # plies 0, 2, 4, … (White)
    black_moves = moves[1::2]  # plies 1, 3, 5, … (Black)
    for i, move in enumerate(white_moves, start=1):
        row[f'White_Move_{i}'] = move
    for i, move in enumerate(black_moves, start=1):
        row[f'Black_Move_{i}'] = move

    return row


def write_csv(games: list[dict], out_path: Path) -> None:
    if not games:
        print('No games found — check your input file.')
        return

    # Gather all column names; keep fixed columns first, then interleaved move columns
    fixed_cols = [
        'Event', 'GameNo', 'White', 'Black',
        'WhiteElo', 'BlackElo', 'WhiteRD', 'BlackRD',
        'TimeControl', 'Date', 'Time', 'ECO', 'PlyCount', 'Result', 'Moves',
    ]
    max_turn = max(
        int(k.split('_')[2])
        for g in games for k in g if k.startswith('White_Move_') or k.startswith('Black_Move_')
    )
    # Interleave: White_Move_1, Black_Move_1, White_Move_2, Black_Move_2, …
    move_cols = [col for i in range(1, max_turn + 1)
                 for col in (f'White_Move_{i}', f'Black_Move_{i}')]
    fieldnames = fixed_cols + move_cols

    with open(out_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        for game in games:
            # Fill missing Move_N columns with empty string
            row = {col: game.get(col, '') for col in fieldnames}
            writer.writerow(row)

    print(f'Wrote {len(games)} games to {out_path}')


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print('Usage: python pgn_to_csv.py <input.txt> <output.csv>')
        sys.exit(1)

    input_path  = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f'Error: file not found — {input_path}')
        sys.exit(1)

    games = parse_pgn(input_path)
    write_csv(games, output_path)
