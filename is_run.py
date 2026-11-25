import hashlib
import json
import os
import random
import select
import sys
import termios
import time
import tty

GAME_TITLE = "इस रन (IS RUN) - 3D"
WIDTH = 36
HEIGHT = 16
DATA_FILE = "is_run_users.json"

ADMIN_PASS = "1234"
LANES = [-1, 0, 1]


def hash_pass(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def save_users(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_users() -> dict:
    default_data = {
        "users": {
            "अंशु प्लेस": {
                "password_hash": hash_pass(ADMIN_PASS),
                "coins": 999999,
                "unlimited_coins": True,
                "is_admin": True,
            }
        }
    }
    if not os.path.exists(DATA_FILE):
        save_users(default_data)
        return default_data
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if "users" not in data:
            data["users"] = {}
        admin_entry = data["users"].get("अंशु प्लेस", {})
        admin_entry["password_hash"] = hash_pass(ADMIN_PASS)
        admin_entry["is_admin"] = True
        admin_entry.setdefault("coins", 999999)
        admin_entry.setdefault("unlimited_coins", True)
        data["users"]["अंशु प्लेस"] = admin_entry
        save_users(data)
        return data
    except Exception:
        save_users(default_data)
        return default_data


def normalize_username(name: str) -> str:
    cleaned = name.strip()
    if cleaned.lower() == "anshu place" or cleaned == "अंशु प्लेस":
        return "अंशु प्लेस"
    return cleaned


def clear():
    os.system("clear")


def auth_menu(data: dict) -> dict:
    users = data["users"]
    while True:
        clear()
        print(f"=== {GAME_TITLE} ===")
        print("1. Login")
        print("2. Register")
        print("3. Exit")
        choice = input("Choose (1/2/3): ").strip()

        if choice == "1":
            raw_user = input("Username: ")
            password = input("Password: ").strip()
            uname = normalize_username(raw_user)
            if uname in users and users[uname]["password_hash"] == hash_pass(password):
                print("Login successful!")
                time.sleep(0.7)
                return users[uname]
            else:
                print("Invalid username or password!")
                time.sleep(1)

        elif choice == "2":
            raw_user = input("New Username: ")
            uname = normalize_username(raw_user)
            if not uname:
                print("Username cannot be empty!")
                time.sleep(1)
                continue
            if uname in users or uname.lower() in {k.lower() for k in users}:
                print("Username already exists!")
                time.sleep(1)
                continue
            password = input("New Password: ").strip()
            if not password:
                print("Password cannot be empty!")
                time.sleep(1)
                continue

            users[uname] = {
                "password_hash": hash_pass(password),
                "coins": 0,
                "unlimited_coins": False,
                "is_admin": False,
            }
            save_users(data)
            print("Registered successfully! Now please login.")
            time.sleep(1)

        elif choice == "3":
            clear()
            print("Bye!")
            sys.exit(0)
        else:
            print("Invalid choice!")
            time.sleep(0.8)


def get_key():
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            ch += sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def project_3d(lane: int, z: float):
    z_clamped = max(0.5, min(12.0, z))
    t = (z_clamped - 0.5) / 11.5
    horizon_y = 2
    bottom_y = HEIGHT - 2
    screen_y = int(round(bottom_y - (1.0 - t) * (bottom_y - horizon_y)))

    half_track = (WIDTH * 0.44) * (1.0 - 0.72 * t)
    center_x = WIDTH // 2
    screen_x = int(round(center_x + lane * (half_track * 0.65)))
    scale = 1.0 - t
    return screen_x, screen_y, scale


def render_3d_frame(player_lane: int, items: list, score: int, user: dict):
    grid = [[" " for _ in range(WIDTH)] for _ in range(HEIGHT)]

    for y in range(2, HEIGHT):
        t = (HEIGHT - 1 - y) / float(HEIGHT - 2)
        half_track = (WIDTH * 0.44) * (1.0 - 0.72 * t)
        cx = WIDTH // 2
        left_rail = int(round(cx - half_track))
        right_rail = int(round(cx + half_track))
        mid_left = int(round(cx - half_track * 0.33))
        mid_right = int(round(cx + half_track * 0.33))

        for rx, ch in [(left_rail, "/"), (right_rail, "\\"), (mid_left, "."), (mid_right, ".")]:
            if 0 <= rx < WIDTH and 0 <= y < HEIGHT:
                if grid[y][rx] == " ":
                    grid[y][rx] = ch

    sorted_items = sorted(items, key=lambda it: it["z"], reverse=True)
    for it in sorted_items:
        sx, sy, scale = project_3d(it["lane"], it["z"])
        if 0 <= sx < WIDTH and 0 <= sy < HEIGHT:
            if it["type"] == "enemy":
                glyph = "#" if scale > 0.65 else ("*" if scale > 0.3 else ".")
            else:
                glyph = "O" if scale > 0.45 else "o"
            grid[sy][sx] = glyph

    px, py, _ = project_3d(player_lane, 0.8)
    for dx, ch in [(-1, "/"), (0, "A"), (1, "\\")]:
        nx = px + dx
        if 0 <= nx < WIDTH and 0 <= py < HEIGHT:
            grid[py][nx] = ch

    clear()
    coin_display = "UNLIMITED" if user.get("unlimited_coins") else str(user.get("coins", 0))
    admin_hint = " | Admin Unlimited Coins: U" if user.get("is_admin") else ""
    print(f"{GAME_TITLE} | Score: {score} | Coins: {coin_display}{admin_hint}")
    print("Lanes: A/Left & D/Right | Quit: Q | Coins: O | Obstacles: #/*")
    print("+" + "-" * WIDTH + "+")
    for row in grid:
        print("|" + "".join(row) + "|")
    print("+" + "-" * WIDTH + "+")


def play_game(user: dict, data: dict):
    player_lane = 0
    items = []
    score = 0
    tick = 0

    try:
        while True:
            tick += 1
            speed = min(1.45, 0.65 + score * 0.002)

            if tick % 5 == 0:
                spawn_lane = random.choice(LANES)
                itype = "coin" if random.random() < 0.35 else "enemy"
                items.append({"type": itype, "lane": spawn_lane, "z": 12.0})

            next_items = []
            for it in items:
                it["z"] -= speed
                cur_lane = LANES[player_lane]

                if it["z"] <= 1.1:
                    if it["lane"] == cur_lane:
                        if it["type"] == "coin":
                            if not user.get("unlimited_coins", False):
                                user["coins"] = user.get("coins", 0) + 1
                            continue
                        elif it["type"] == "enemy":
                            save_users(data)
                            render_3d_frame(cur_lane, items, score, user)
                            coin_display = "UNLIMITED" if user.get("unlimited_coins") else str(user.get("coins", 0))
                            print(f"=== GAME OVER ({GAME_TITLE}) ===")
                            print(f"Final Score: {score} | Coins: {coin_display}")
                            return
                if it["z"] > 0.2:
                    next_items.append(it)

            items = next_items

            if select.select([sys.stdin], [], [], 0.11)[0]:
                key = get_key()
                if key in ("a", "A", "\x1b[D") and player_lane > 0:
                    player_lane -= 1
                elif key in ("d", "D", "\x1b[C") and player_lane < len(LANES) - 1:
                    player_lane += 1
                elif key in ("u", "U") and user.get("is_admin", False):
                    user["unlimited_coins"] = True
                    user["coins"] = 999999999
                    save_users(data)
                elif key in ("q", "Q"):
                    save_users(data)
                    clear()
                    coin_display = "UNLIMITED" if user.get("unlimited_coins") else str(user.get("coins", 0))
                    print(f"Quit {GAME_TITLE}! Final Score: {score} | Coins: {coin_display}")
                    return

            score += 1
            render_3d_frame(LANES[player_lane], items, score, user)
            time.sleep(0.03)
    except KeyboardInterrupt:
        save_users(data)
        clear()
        print(f"Stopped {GAME_TITLE}! Score: {score}")


def main():
    data = load_users()
    while True:
        user = auth_menu(data)
        play_game(user, data)
        again = input("Play again? (y/n): ").strip().lower()
        if again != "y":
            break


if __name__ == "__main__":
    main()
