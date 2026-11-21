import os, sys, time, math, random, hashlib, getpass, sqlite3, socket, threading, json

from PIL import Image, ImageFile

try:
    import mysql.connector
    MA_MYSQL = True
except ImportError:
    MA_MYSQL = False

ESC = chr(27)

if os.name == "nt":
    os.system("")

# ============================================================
# KONFIGURACJA BAZY DANYCH MYSQL
# ============================================================

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",          # <--- wpisz swoje hasło do lokalnego MySQL
    "database": "cmd_raycast",
    "port": 3306
}

PLIK_SQLITE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "cmd_raycast_local.db"
)

if os.name == 'nt':
    import ctypes, msvcrt
    u32 = ctypes.windll.user32

    def klawisze():
        while msvcrt.kbhit():
            msvcrt.getch()

        k = set()
        kody = (
            (0x26, 'UP'), (0x28, 'DOWN'),
            (0x25, 'LEFT'), (0x27, 'RIGHT'),
            (0x57, 'W'), (0x53, 'S'),
            (0x41, 'A'), (0x44, 'D'),
            (0x20, 'SPACE'), (0x43, 'C'),
            (0x51, 'Q'), (0x52, 'R'),
            (0x4D, 'M')
        )

        for kod, zn in kody:
            if u32.GetAsyncKeyState(kod) & 0x8000:
                k.add(zn)

        return k

else:
    import tty, termios, select

    def klawisze():
        k = set()

        while select.select([sys.stdin], [], [], 0):
            c = sys.stdin.read(1)

            if c == ESC:
                k.add({
                    '[A': 'UP',
                    '[B': 'DOWN',
                    '[D': 'LEFT',
                    '[C': 'RIGHT'
                }.get(sys.stdin.read(2), ''))

            elif c == ' ':
                k.add('SPACE')

            else:
                k.add(c.upper())

        return k


# ============================================================
# SYSTEM DŹWIĘKOWY W TLE (FOLDER SOUNDS/ - BEZ BLOKOWANIA FPS)
# ============================================================

class Dzwiek:

    def __init__(self):
        self.wlaczony = True
        self.ostatni_sfx = {}
        self.folder = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "sounds"
        )
        self.muzyka_gra = False

    def _mci(self, komenda):
        if os.name == 'nt':
            ctypes.windll.winmm.mciSendStringW(komenda, None, 0, None)

    def start_muzyki(self):
        if not self.wlaczony or os.name != 'nt':
            return

        for nazwa in ("music.mp3", "music.wav"):
            sciezka = os.path.join(self.folder, nazwa)
            if os.path.exists(sciezka):
                self._mci("close bgm")
                self._mci(f'open "{sciezka}" alias bgm')
                self._mci("play bgm repeat")
                self.muzyka_gra = True
                break

    def stop_muzyki(self):
        if self.muzyka_gra:
            self._mci("stop bgm")
            self._mci("close bgm")
            self.muzyka_gra = False

    def sfx(self, plik, min_odstep=0.25):
        if not self.wlaczony or os.name != 'nt':
            return

        teraz = time.perf_counter()

        if teraz - self.ostatni_sfx.get(plik, 0.0) < min_odstep:
            return

        sciezka = os.path.join(self.folder, plik)

        if not os.path.exists(sciezka):
            return

        self.ostatni_sfx[plik] = teraz
        alias = f"sfx_{plik.replace('.', '_')}_{int(teraz * 1000) % 100000}"

        def _watek():
            try:
                self._mci(f'open "{sciezka}" alias {alias}')
                self._mci(f"play {alias} wait")
                self._mci(f"close {alias}")
            except Exception:
                pass

        threading.Thread(target=_watek, daemon=True).start()


# ============================================================
# USTAWIENIA EKRANU I TŁA
# ============================================================

W, H = 80, 24

PLIK_TLA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background.png")
PLIK_SCIANY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wall.png")

R, CZ, ZO, SZ, ZI, BI, NI, CY, FI, RO, BR, ZL, PO = (
    f"{ESC}[0m",
    f"{ESC}[91m",
    f"{ESC}[93m",
    f"{ESC}[90m",
    f"{ESC}[92m",
    f"{ESC}[97m",
    f"{ESC}[94m",
    f"{ESC}[96m",
    f"{ESC}[95m",
    f"{ESC}[38;2;255;105;180m",
    f"{ESC}[38;2;139;69;19m",
    f"{ESC}[38;2;255;215;0m",
    f"{ESC}[38;2;255;140;0m"
)

MAPA_SKINOW = {
    "NI": ("Niebieski Klasyk", NI, 0),
    "CZ": ("Czerwony Wyścigowy", CZ, 150),
    "CY": ("Cyberpunk Cyjan", CY, 250),
    "RO": ("Neonowy Róż", RO, 350),
    "PO": ("Pomarańczowy GT", PO, 450),
    "ZL": ("Złoty Mistrzowski", ZL, 800),
}

PRESETY = {
    "1": {
        "nazwa": "Łatwy (Rozgrzewka)",
        "nagroda": 100,
        "konfig": [
            (3, 0.38, -1.2, CZ),
            (3, 0.39,  1.2, ZO),
            (3, 0.40,  0.0, FI),
            (3, 0.41, -0.6, CY),
            (3, 0.42,  0.6, BI),
        ]
    },
    "2": {
        "nazwa": "Normalny (Zbalansowany Peleton)",
        "nagroda": 250,
        "konfig": [
            (3, 0.44, -1.2, CZ),
            (3, 0.45,  1.2, ZO),
            (3, 0.46,  0.0, FI),
            (3, 0.47, -1.2, NI),
            (3, 0.48,  1.2, CY),
            (3, 0.49, -0.6, BI),
            (3, 0.50,  0.8, CZ),
        ]
    },
    "3": {
        "nazwa": "Hardcore (Unnerfed Impossible)",
        "nagroda": 600,
        "konfig": [
            (3,  0.46, -1.2, CZ),
            (3,  0.47,  1.2, ZO),
            (6,  0.49,  0.0, FI),
            (9,  0.51, -1.2, RO),
            (9,  0.52,  1.2, CY),
            (12, 0.54, -0.6, PO),
            (14, 0.56,  0.8, ZL),
        ]
    }
}


# ============================================================
# BAZA DANYCH (MYSQL + FALLBACK SQLITE) I SZYFROWANIE HASEŁ
# ============================================================

class BazaDanych:

    def __init__(self):
        self.tryb = "offline"
        self.conn = None
        self._polacz()

    def _polacz(self):
        if MA_MYSQL:
            try:
                cfg_init = {
                    k: v for k, v in MYSQL_CONFIG.items()
                    if k != "database"
                }

                tmp = mysql.connector.connect(**cfg_init, connection_timeout=2)
                cur = tmp.cursor()
                cur.execute(
                    f"CREATE DATABASE IF NOT EXISTS {MYSQL_CONFIG['database']} "
                    f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
                tmp.close()

                self.conn = mysql.connector.connect(**MYSQL_CONFIG)
                self.tryb = "mysql"
                self._utworz_tabele()
                return

            except Exception:
                pass

        self.conn = sqlite3.connect(PLIK_SQLITE)
        self.conn.row_factory = sqlite3.Row
        self.tryb = "sqlite"
        self._utworz_tabele()

    def _ph(self):
        return "%s" if self.tryb == "mysql" else "?"

    def _utworz_tabele(self):
        cur = self.conn.cursor()

        if self.tryb == "mysql":
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gracze (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nick VARCHAR(32) NOT NULL UNIQUE,
                    haslo_hash VARCHAR(128) NOT NULL,
                    sol VARCHAR(64) NOT NULL,
                    kasa INT NOT NULL DEFAULT 100,
                    wybrany_skin VARCHAR(8) NOT NULL DEFAULT 'NI',
                    odblokowane_skiny VARCHAR(255) NOT NULL DEFAULT 'NI',
                    buff_silnik INT NOT NULL DEFAULT 0,
                    buff_opony INT NOT NULL DEFAULT 0,
                    rekord_czas FLOAT DEFAULT NULL
                )
            """)
        else:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS gracze (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nick TEXT NOT NULL UNIQUE,
                    haslo_hash TEXT NOT NULL,
                    sol TEXT NOT NULL,
                    kasa INTEGER NOT NULL DEFAULT 100,
                    wybrany_skin TEXT NOT NULL DEFAULT 'NI',
                    odblokowane_skiny TEXT NOT NULL DEFAULT 'NI',
                    buff_silnik INTEGER NOT NULL DEFAULT 0,
                    buff_opony INTEGER NOT NULL DEFAULT 0,
                    rekord_czas REAL DEFAULT NULL
                )
            """)

        self.conn.commit()

    def zahashuj(self, haslo, sol_hex=None):
        sol = bytes.fromhex(sol_hex) if sol_hex else os.urandom(16)
        skrot = hashlib.pbkdf2_hmac(
            "sha256",
            haslo.encode("utf-8"),
            sol,
            100_000
        )
        return skrot.hex(), sol.hex()

    def pobierz_gracza(self, nick):
        p = self._ph()

        if self.tryb == "mysql":
            cur = self.conn.cursor(dictionary=True)
            cur.execute(f"SELECT * FROM gracze WHERE nick = {p}", (nick,))
            return cur.fetchone()
        else:
            cur = self.conn.cursor()
            cur.execute(f"SELECT * FROM gracze WHERE nick = {p}", (nick,))
            row = cur.fetchone()
            return dict(row) if row else None

    def zarejestruj(self, nick, haslo):
        if self.pobierz_gracza(nick):
            return False, "Ten nick jest już zajęty!"

        h_hash, sol = self.zahashuj(haslo)
        p = self._ph()
        cur = self.conn.cursor()

        cur.execute(
            f"INSERT INTO gracze (nick, haslo_hash, sol) VALUES ({p}, {p}, {p})",
            (nick, h_hash, sol)
        )
        self.conn.commit()

        return True, "Konto utworzone! Otrzymujesz 100$ na start."

    def zaloguj(self, nick, haslo):
        gracz = self.pobierz_gracza(nick)

        if not gracz:
            return None, "Nie znaleziono takiego gracza."

        h_check, _ = self.zahashuj(haslo, gracz["sol"])
        if h_check != gracz["haslo_hash"]:
            return None, "Nieprawidłowe hasło!"
        return gracz, "Zalogowano pomyślnie."

    def wykonaj_update(self, sql_template, params):
        p = self._ph()
        sql = sql_template.replace("?", p)
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()

    def top_rekordy(self):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT nick, rekord_czas FROM gracze "
            "WHERE rekord_czas IS NOT NULL "
            "ORDER BY rekord_czas ASC LIMIT 5"
        )
        return cur.fetchall()


# ============================================================
# SERWER / MULTIPLAYER LAN (TCP)
# ============================================================

class SiecLAN:

    def __init__(self):
        self.aktywna = False
        self.czy_host = False
        self.sock = None
        self.klienci = []
        self.gracze_zdalni = {}
        self.lock = threading.Lock()
        self.dane_toru = None

    def uruchom_hosta(self, port, dane_toru):
        self.czy_host = True
        self.aktywna = True
        self.dane_toru = dane_toru
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", port))
        self.sock.listen(5)
        threading.Thread(
            target=self._akceptuj_klientow,
            daemon=True
        ).start()

    def _akceptuj_klientow(self):
        while self.aktywna:
            try:
                conn, addr = self.sock.accept()
                pakiet_mapa = json.dumps({
                    "typ": "MAPA",
                    "dane": self.dane_toru
                }) + "\n"
                conn.sendall(pakiet_mapa.encode("utf-8"))
                self.klienci.append(conn)
                threading.Thread(
                    target=self._obsluz_klienta,
                    args=(conn,),
                    daemon=True
                ).start()
            except Exception:
                break

    def _obsluz_klienta(self, conn):
        buf = ""
        while self.aktywna:
            try:
                data = conn.recv(4096).decode("utf-8")
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    linia, buf = buf.split("\n", 1)
                    msg = json.loads(linia)
                    if msg.get("typ") == "POZ":
                        with self.lock:
                            self.gracze_zdalni[msg["nick"]] = msg
                        for k in list(self.klienci):
                            if k != conn:
                                try:
                                    k.sendall((linia + "\n").encode("utf-8"))
                                except Exception:
                                    pass
            except Exception:
                break

    def polacz_jako_klient(self, ip, port):
        self.czy_host = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((ip, port))
        self.sock.settimeout(None)
        self.aktywna = True
        buf = ""
        while "\n" not in buf:
            buf += self.sock.recv(8192).decode("utf-8")
        linia, reszta = buf.split("\n", 1)
        msg = json.loads(linia)
        self.dane_toru = msg["dane"]
        threading.Thread(
            target=self._odbieraj_od_hosta,
            args=(reszta,),
            daemon=True
        ).start()

    def _odbieraj_od_hosta(self, bufor_startowy):
        buf = bufor_startowy
        while self.aktywna:
            try:
                data = self.sock.recv(4096).decode("utf-8")
                if not data:
                    break
                buf += data
                while "\n" in buf:
                    linia, buf = buf.split("\n", 1)
                    msg = json.loads(linia)
                    if msg.get("typ") == "POZ":
                        with self.lock:
                            self.gracze_zdalni[msg["nick"]] = msg
            except Exception:
                break

    def wyslij_pozycje(self, nick, x, y, kol_kod, postep):
        if not self.aktywna:
            return
        pakiet = json.dumps({
            "typ": "POZ",
            "nick": nick,
            "x": round(x, 2),
            "y": round(y, 2),
            "kol": kol_kod,
            "postep": round(postep, 2)
        }) + "\n"
        dane = pakiet.encode("utf-8")
        if self.czy_host:
            for k in list(self.klienci):
                try:
                    k.sendall(dane)
                except Exception:
                    pass
        else:
            try:
                self.sock.sendall(dane)
            except Exception:
                pass


# ============================================================
# MENU GŁÓWNE I SKLEP
# ============================================================

def wyczysc_ekran():
    os.system("cls" if os.name == "nt" else "clear")


def menu_glowne(baza):
    gracz = None
    wybrany_preset = "2"
    siec = SiecLAN()
    while True:
        wyczysc_ekran()
        status_db = (
            f"{ZI}MySQL ({MYSQL_CONFIG['database']}){R}"
            if baza.tryb == "mysql"
            else f"{ZO}SQLite (Lokalny Fallback){R}"
        )
        print(f"{CY}=============================================={R}")
        print(f"{BI}         CMD-RAYCAST :: LOGOWANIE             {R}")
        print(f"{CY}=============================================={R}")
        print(f"Baza danych: {status_db}\n")
        print("1. Zaloguj się")
        print("2. Zarejestruj nowe konto")
        print("3. Graj jako Gość (bez zapisu)")
        print("0. Wyjście")
        w = input("\nWybór: ").strip()
        if w == "0":
            sys.exit(0)
        elif w == "3":
            break
        elif w in ("1", "2"):
            nick = input("Nick: ").strip()
            haslo = getpass.getpass("Hasło (niewidoczne podczas pisania): ").strip()
            if not nick or not haslo:
                continue
            if w == "1":
                g, msg = baza.zaloguj(nick, haslo)
                print(f"{ZI if g else CZ}{msg}{R}")
                time.sleep(1.0)
                if g:
                    gracz = g
                    break
            else:
                ok, msg = baza.zarejestruj(nick, haslo)
                print(f"{ZI if ok else CZ}{msg}{R}")
                time.sleep(1.2)
                if ok:
                    gracz = baza.pobierz_gracza(nick)
                    break

    while True:
        if gracz:
            gracz = baza.pobierz_gracza(gracz["nick"])
        wyczysc_ekran()
        nick_wysw = (
            f"{ZI}{gracz['nick']}{R} | Portfel: {ZL}{gracz['kasa']}${R}"
            if gracz
            else f"{ZO}Gość{R}"
        )
        skin_kod = gracz["wybrany_skin"] if gracz else "NI"
        skin_nazwa, skin_ansi, _ = MAPA_SKINOW[skin_kod]
        b_silnik = gracz["buff_silnik"] if gracz else 0
        b_opony = gracz["buff_opony"] if gracz else 0
        print(f"{CY}=============================================={R}")
        print(f"{BI}         CMD-RAYCAST :: MENU GŁÓWNE           {R}")
        print(f"{CY}=============================================={R}")
        print(f"Gracz:  {nick_wysw}")
        print(f"Auto:   {skin_ansi}{skin_nazwa}{R}")
        print(f"Buffy:  Silnik Lv.{b_silnik}/3 | Opony Lv.{b_opony}/3")
        print(f"Preset: {ZO}{PRESETY[wybrany_preset]['nazwa']}{R} (+{PRESETY[wybrany_preset]['nagroda']}$/okr.)")
        print("----------------------------------------------")
        print("1. START WYŚCIGU (Singleplayer vs Boty)")
        print("2. Zmień preset trudności")
        if gracz:
            print("3. Garaż i Sklep (Skiny oraz Buffy)")
            print("4. Multiplayer LAN (Postaw serwer / Dołącz)")
            print("5. Tabela rekordów okrążeń (SQL TOP 5)")
        print("0. Wyjście")
        wyb = input("\nWybierz opcję: ").strip()

        if wyb == "1":
            return {
                "gracz": gracz,
                "preset": PRESETY[wybrany_preset],
                "skin_kod": skin_kod,
                "skin_ansi": skin_ansi,
                "vmax_mult": 1.0 + b_silnik * 0.015,
                "grip_mult": 1.0 + b_opony * 0.04,
                "siec": siec
            }
        elif wyb == "2":
            wyczysc_ekran()
            print(f"{CY}--- WYBIERZ PRESET TRUDNOŚCI ---{R}\n")
            for k, p in PRESETY.items():
                print(f"{k}. {p['nazwa']} - Nagroda za okrążenie: {ZL}{p['nagroda']}${R}")
            pw = input("\nWybór: ").strip()
            if pw in PRESETY:
                wybrany_preset = pw
        elif wyb == "3" and gracz:
            while True:
                gracz = baza.pobierz_gracza(gracz["nick"])
                odbl = gracz["odblokowane_skiny"].split(",")
                wyczysc_ekran()
                print(f"{ZL}=== GARAŻ I SKLEP ({gracz['nick']} | Kasa: {gracz['kasa']}$) ==={R}\n")
                print(f"{CY}Skiny samochodu:{R}")
                kody = list(MAPA_SKINOW.keys())
                for idx, k in enumerate(kody, 1):
                    naz, ans, cena = MAPA_SKINOW[k]
                    st = (
                        f"{ZI}[ZAŁOŻONY]{R}"
                        if gracz["wybrany_skin"] == k
                        else (
                            f"{BI}[POSIADANY]{R}"
                            if k in odbl
                            else f"{ZO}[{cena}$]{R}"
                        )
                    )
                    print(f"  {idx}. {ans}{naz}{R} {st}")
                c_sil = (gracz["buff_silnik"] + 1) * 200
                c_opo = (gracz["buff_opony"] + 1) * 200
                print(f"\n{CY}Lekkie Buffy (maks. poziom 3):{R}")
                print(
                    f"  7. Tuning ECU (+1.5% V-max) [Lv.{gracz['buff_silnik']}/3] - "
                    f"{c_sil if gracz['buff_silnik'] < 3 else 'MAX'}$"
                )
                print(
                    f"  8. Opony Sport (+4% przyczepności) [Lv.{gracz['buff_opony']}/3] - "
                    f"{c_opo if gracz['buff_opony'] < 3 else 'MAX'}$"
                )
                print("  0. Powrót")
                sw = input("\nWybierz pozycję: ").strip()
                if sw == "0":
                    break
                elif sw in [str(i) for i in range(1, len(kody) + 1)]:
                    k = kody[int(sw) - 1]
                    _, _, cena = MAPA_SKINOW[k]
                    if k in odbl:
                        baza.wykonaj_update(
                            "UPDATE gracze SET wybrany_skin = ? WHERE id = ?",
                            (k, gracz["id"])
                        )
                    elif gracz["kasa"] >= cena:
                        nowe = ",".join(odbl + [k])
                        baza.wykonaj_update(
                            "UPDATE gracze SET kasa = kasa - ?, odblokowane_skiny = ?, wybrany_skin = ? WHERE id = ?",
                            (cena, nowe, k, gracz["id"])
                        )
                elif sw == "7" and gracz["buff_silnik"] < 3 and gracz["kasa"] >= c_sil:
                    baza.wykonaj_update(
                        "UPDATE gracze SET kasa = kasa - ?, buff_silnik = buff_silnik + 1 WHERE id = ?",
                        (c_sil, gracz["id"])
                    )
                elif sw == "8" and gracz["buff_opony"] < 3 and gracz["kasa"] >= c_opo:
                    baza.wykonaj_update(
                        "UPDATE gracze SET kasa = kasa - ?, buff_opony = buff_opony + 1 WHERE id = ?",
                        (c_opo, gracz["id"])
                    )
        elif wyb == "4":
            wyczysc_ekran()
            print(f"{CY}--- MULTIPLAYER LAN ---{R}\n")
            print("1. Postaw serwer (Host)")
            print("2. Dołącz do serwera (Klient)")
            print("0. Powrót")
            mw = input("\nWybór: ").strip()
            if mw == "1":
                port = int(input("Port (domyślnie 5555): ").strip() or "5555")
                dane_toru = generuj_tor(512)
                siec.uruchom_hosta(port, dane_toru)
                print(f"{ZI}Serwer nasłuchuje na porcie {port}! Uruchamiam wyścig...{R}")
                time.sleep(1.0)
                return {
                    "gracz": gracz,
                    "preset": PRESETY[wybrany_preset],
                    "skin_kod": skin_kod,
                    "skin_ansi": skin_ansi,
                    "vmax_mult": 1.0 + b_silnik * 0.015,
                    "grip_mult": 1.0 + b_opony * 0.04,
                    "siec": siec
                }
            elif mw == "2":
                ip = input("IP Hosta (np. 127.0.0.1): ").strip() or "127.0.0.1"
                port = int(input("Port (domyślnie 5555): ").strip() or "5555")
                try:
                    siec.polacz_jako_klient(ip, port)
                    print(f"{ZI}Połączono z serwerem!{R}")
                    time.sleep(1.0)
                    return {
                        "gracz": gracz,
                        "preset": PRESETY[wybrany_preset],
                        "skin_kod": skin_kod,
                        "skin_ansi": skin_ansi,
                        "vmax_mult": 1.0 + b_silnik * 0.015,
                        "grip_mult": 1.0 + b_opony * 0.04,
                        "siec": siec
                    }
                except Exception as e:
                    print(f"{CZ}Błąd połączenia: {e}{R}")
                    time.sleep(1.5)
        elif wyb == "5":
            wyczysc_ekran()
            print(f"{ZL}=== TOP 5 REKORDÓW OKRĄŻEŃ ==={R}\n")
            rekordy = baza.top_rekordy()
            if not rekordy:
                print("Brak zapisanych rekordów.")
            else:
                for i, r in enumerate(rekordy, 1):
                    n_txt = r["nick"] if isinstance(r, dict) else r[0]
                    c_txt = r["rekord_czas"] if isinstance(r, dict) else r[1]
                    print(f"{i}. {BI}{n_txt:<15}{R} -> {ZI}{c_txt:.2f}s{R}")
            input("\nWciśnij ENTER...")
        elif wyb == "0":
            sys.exit(0)


# ============================================================
# PANORAMA 360° I TEKSTURA ŚCIAN
# ============================================================

ImageFile.LOAD_TRUNCATED_IMAGES = True
PANORAMA_FOV_H = 72.0
PANORAMA_FOV_V = 55.0
PANORAMA_PITCH = 0.0
PANORAMA_OFFSET = 0.0


def zaladuj_panorame(nazwa):
    try:
        obraz = Image.open(nazwa).convert("RGB")
        if obraz.width != obraz.height * 2:
            raise ValueError(
                f"Panorama 360° musi mieć proporcje 2:1; "
                f"plik ma {obraz.width}x{obraz.height}."
            )
        return obraz
    except Exception as e:
        print("Nie udało się załadować panoramy:", e)
        return None


def zaladuj_teksture_sciany(nazwa):
    """Wczytuje wall.png lub generuje proceduralną teksturę 32x32 cyberpunkowej bandy."""
    try:
        obraz = Image.open(nazwa).convert("RGB")
        w, h = obraz.size
        pix = obraz.load()
        siatka = [[pix[x, y] for x in range(w)] for y in range(h)]
        return siatka, w, h
    except Exception:
        w, h = 32, 32
        siatka = []
        for y in range(h):
            wiersz = []
            for x in range(w):
                if y < 4 or y >= h - 4:
                    if ((x + y) // 4) % 2 == 0:
                        wiersz.append((220, 40, 60))
                    else:
                        wiersz.append((235, 235, 240))
                elif 14 <= y <= 17:
                    if (x // 4) % 2 == 0:
                        wiersz.append((0, 235, 255))
                    else:
                        wiersz.append((255, 50, 180))
                else:
                    if x % 8 == 0 or y % 8 == 0:
                        wiersz.append((28, 32, 42))
                    else:
                        wiersz.append((55, 62, 78))
            siatka.append(wiersz)
        return siatka, w, h


def renderuj_panorame(panorama, szerokosc, liczba_wierszy, kat):
    """Rzutuje panoramę 360° na widok kamery, z zawijaniem poziomym."""
    if panorama is None:
        return [[' '] * szerokosc for _ in range(liczba_wierszy)]
    pw, ph = panorama.size
    piksele = panorama.load()
    wysokosc_px = max(1, liczba_wierszy * 2)
    fov_h = math.radians(PANORAMA_FOV_H)
    fov_v = math.radians(PANORAMA_FOV_V)
    pitch = math.radians(PANORAMA_PITCH)
    offset = math.radians(PANORAMA_OFFSET)
    polowa_tan = math.tan(fov_h / 2.0)
    wynik = []
    for y in range(liczba_wierszy):
        wiersz = []
        for x in range(szerokosc):
            ekran_x = (2.0 * (x + 0.5) / szerokosc) - 1.0
            kat_x = math.atan(ekran_x * polowa_tan)
            azymut = kat + offset + kat_x
            px = int(((azymut / (2.0 * math.pi) + 0.5) % 1.0) * pw)
            px = min(pw - 1, max(0, px))
            indeks_gora = y * 2
            indeks_dol = indeks_gora + 1
            elewacja_gora = pitch + (
                0.5 - (indeks_gora + 0.5) / wysokosc_px
            ) * fov_v
            elewacja_dol = pitch + (
                0.5 - (indeks_dol + 0.5) / wysokosc_px
            ) * fov_v
            py_gora = int((0.5 - elewacja_gora / math.pi) * ph)
            py_dol = int((0.5 - elewacja_dol / math.pi) * ph)
            py_gora = min(ph - 1, max(0, py_gora))
            py_dol = min(ph - 1, max(0, py_dol))
            r1, g1, b1 = piksele[px, py_gora]
            r2, g2, b2 = piksele[px, py_dol]
            wiersz.append(
                f"{ESC}[38;2;{r1};{g1};{b1}m"
                f"{ESC}[48;2;{r2};{g2};{b2}m"
                f"▀{R}"
            )
        wynik.append(wiersz)
    return wynik


# ============================================================
# GENEROWANIE TORU (Z BOOST PADAMI '3')
# ============================================================

def generuj_tor(rozmiar=512):
    pedzel = [
        (dx, dy)
        for dy in range(-3, 4)
        for dx in range(-3, 4)
        if dx * dx + dy * dy <= 9
    ]
    N = 14
    krok = (rozmiar - 48) / float(N)
    while True:
        cykl = [(x, 1) for x in range(1, N - 1)]
        cykl += [(N - 2, y) for y in range(2, N - 1)]
        cykl += [(x, N - 2) for x in range(N - 3, 0, -1)]
        cykl += [(1, y) for y in range(N - 3, 1, -1)]
        zajete = set(cykl)
        for _ in range(180):
            idx = random.randrange(len(cykl))
            x1, y1 = cykl[idx]
            x2, y2 = cykl[(idx + 1) % len(cykl)]
            nx, ny = -(y2 - y1), (x2 - x1)
            if random.random() < 0.5:
                nx, ny = -nx, -ny
            p1x, p1y = x1 + nx, y1 + ny
            p2x, p2y = x2 + nx, y2 + ny
            p1, p2 = (p1x, p1y), (p2x, p2y)
            if (
                1 <= p1x < N - 1 and
                1 <= p1y < N - 1 and
                1 <= p2x < N - 1 and
                1 <= p2y < N - 1 and
                p1 not in zajete and
                p2 not in zajete
            ):
                dozwolone = {
                    (x1, y1),
                    (x2, y2),
                    p1,
                    p2
                }
                kolizja = False
                for px, py in (p1, p2):
                    for ox in (-1, 0, 1):
                        for oy in (-1, 0, 1):
                            if (
                                (px + ox, py + oy) in zajete
                                and
                                (px + ox, py + oy) not in dozwolone
                            ):
                                kolizja = True
                if not kolizja:
                    cykl.insert(idx + 1, p2)
                    cykl.insert(idx + 1, p1)
                    zajete.add(p1)
                    zajete.add(p2)
        if len(cykl) < 42:
            continue
        punkty = []
        for gx, gy in cykl:
            px = 24 + (
                gx + 0.5 + random.uniform(-0.24, 0.24)
            ) * krok
            py = 24 + (
                gy + 0.5 + random.uniform(-0.24, 0.24)
            ) * krok
            punkty.append((px, py))
        for _ in range(2):
            nowe = []
            for i in range(len(punkty)):
                x1, y1 = punkty[i]
                x2, y2 = punkty[(i + 1) % len(punkty)]
                nowe.append((
                    0.75 * x1 + 0.25 * x2,
                    0.75 * y1 + 0.25 * y2
                ))
                nowe.append((
                    0.25 * x1 + 0.75 * x2,
                    0.25 * y1 + 0.75 * y2
                ))
            punkty = nowe
        siatka = [
            bytearray(b'1' * rozmiar)
            for _ in range(rozmiar)
        ]
        odwiedzone = set()
        n = len(punkty)
        for i in range(n):
            x1, y1 = punkty[i]
            x2, y2 = punkty[(i + 1) % n]
            kroki = int(
                math.hypot(x2 - x1, y2 - y1) * 1.5
            ) + 1
            for s in range(kroki + 1):
                t = s / float(kroki)
                cx = int(x1 + (x2 - x1) * t)
                cy = int(y1 + (y2 - y1) * t)
                if (cx, cy) not in odwiedzone:
                    odwiedzone.add((cx, cy))
                    for dx, dy in pedzel:
                        nx, ny = cx + dx, cy + dy
                        if (
                            5 <= nx < rozmiar - 5 and
                            5 <= ny < rozmiar - 5
                        ):
                            siatka[ny][nx] = 46
        (sx, sy), (nx, ny) = punkty[:2]
        ang = math.atan2(ny - sy, nx - sx)
        dx, dy = math.cos(ang), math.sin(ang)
        if any(
            siatka[int(sy + dy * k)][int(sx + dx * k)] != 46
            for k in (-2, -1, 0, 1, 2)
        ):
            continue
        for w in range(-4, 5):
            gx = int(sx - dx * 2 - dy * w)
            gy = int(sy - dy * 2 + dx * w)
            if (
                2 <= gx < rozmiar - 2 and
                2 <= gy < rozmiar - 2 and
                siatka[gy][gx] == 46
            ):
                siatka[gy][gx] = 50
        # Rozmieszczanie Boost Padów ('3' = kod ASCII 51) na asfalcie
        for idx_bp in range(18, n - 10, 26):
            bx, by = punkty[idx_bp]
            ibx, iby = int(bx), int(by)
            for oy in range(-1, 2):
                for ox in range(-1, 2):
                    px_b, py_b = ibx + ox, iby + oy
                    if (
                        5 <= px_b < rozmiar - 5 and
                        5 <= py_b < rozmiar - 5 and
                        siatka[py_b][px_b] == 46
                    ):
                        siatka[py_b][px_b] = 51
        return (
            [w.decode('ascii') for w in siatka],
            sx, sy, dx, dy, punkty
        )


# ============================================================
# FUNKCJE POMOCNICZE
# ============================================================

def obroc(x, y, a):
    return (
        x * math.cos(a) - y * math.sin(a),
        x * math.sin(a) + y * math.cos(a)
    )


def utworz_boty(sciezka, konfig):
    boty = []
    n = len(sciezka)
    for idx_pkt, v_baz, pas, kol in konfig:
        x1, y1 = sciezka[idx_pkt % n]
        x2, y2 = sciezka[(idx_pkt + 1) % n]
        ang = math.atan2(y2 - y1, x2 - x1)
        dx, dy = math.cos(ang), math.sin(ang)
        boty.append({
            'x': x1 - dy * pas,
            'y': y1 + dx * pas,
            'dx': dx,
            'dy': dy,
            'vx': 0.0,
            'vy': 0.0,
            'idx': (idx_pkt + 1) % n,
            'lap': 0,
            'v_baz': v_baz,
            'pas': pas,
            'kol': kol,
            'boost_do': 0.0
        })
    return boty


def znajdz_indeks_sciezki(x, y, sciezka, podpowiedz=0):
    n = len(sciezka)
    naj_idx = podpowiedz % n
    naj_d = 1e18
    for off in range(-25, 26):
        idx = (podpowiedz + off) % n
        sx, sy = sciezka[idx]
        d = (x - sx) ** 2 + (y - sy) ** 2
        if d < naj_d:
            naj_d = d
            naj_idx = idx
    return naj_idx


def sprawdz_zakret(MAPA, cx, cy, dx, dy, kmh):
    if kmh < 75:
        return "", ""
    dyst_przod = 34.0
    for d in range(2, 35):
        if MAPA[int(cy + dy * d)][int(cx + dx * d)] == '1':
            dyst_przod = float(d)
            break
    if dyst_przod > 26.0:
        return "", ""
    lx, ly = obroc(dx, dy, -0.6)
    rx, ry = obroc(dx, dy, 0.6)
    wl, wp = 0, 0
    for d in range(2, 32):
        if MAPA[int(cy + ly * d)][int(cx + lx * d)] != '1':
            wl += 1
        else:
            break
    for d in range(2, 32):
        if MAPA[int(cy + ry * d)][int(cx + rx * d)] != '1':
            wp += 1
        else:
            break
    metry = int(dyst_przod * 3)
    ostry = dyst_przod < 15.0
    kolor = CZ if ostry else ZO
    if wl > wp + 3:
        txt = (
            f"<<< OSTRY LEWY! ({metry}m)"
            if ostry else
            f"<< LEWY ({metry}m)"
        )
    elif wp > wl + 3:
        txt = (
            f"OSTRY PRAWY! >>> ({metry}m)"
            if ostry else
            f"PRAWY >> ({metry}m)"
        )
    else:
        txt = f"!!! UWAGA ZAKRET ({metry}m) !!!"
    return txt, kolor


# ============================================================
# GŁÓWNA GRA
# ============================================================

def gra(baza, sesja):
    ROZMIAR = 512
    siec = sesja["siec"]
    gracz = sesja["gracz"]
    preset = sesja["preset"]
    kolor_gracza = sesja["skin_ansi"]
    nick_gracza = gracz["nick"] if gracz else f"Gosc_{random.randint(100, 999)}"
    dzwiek = Dzwiek()
    if siec.aktywna and siec.dane_toru:
        MAPA, cx, cy, dx, dy, sciezka = siec.dane_toru
    else:
        MAPA, cx, cy, dx, dy, sciezka = generuj_tor(ROZMIAR)
    boty = [] if siec.aktywna else utworz_boty(sciezka, preset["konfig"])
    px, py = -dy * 0.72, dx * 0.72
    v = 0.0
    max_v = 0.46 * sesja["vmax_mult"]
    skr = 0.0
    t0 = time.time()
    rek = gracz["rekord_czas"] if (gracz and gracz.get("rekord_czas")) else None
    komunikat_hud = ""
    komunikat_czas = 0.0
    ostatnia_klatka = time.perf_counter()
    fps = 0.0
    z_dala = False
    vel_x, vel_y = 0.0, 0.0
    nitro = 100.0
    boost_pad_do = 0.0
    ostatni_pad_czas = 0.0
    tpp = True
    c_wcisniete = False
    m_wcisniete = False
    start_x, start_y = cx, cy
    gracz_lap = 0
    gracz_idx = 0
    n_sc = len(sciezka)
    panorama = zaladuj_panorame(PLIK_TLA)
    tex_sciana, tex_w, tex_h = zaladuj_teksture_sciany(PLIK_SCIANY)
    sys.stdout.write(f"{ESC}[?25l{ESC}[2J")
    dzwiek.start_muzyki()
    if os.name != 'nt':
        fd = sys.stdin.fileno()
        st = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    try:
        while True:
            teraz = time.perf_counter()
            dt_klatki = teraz - ostatnia_klatka
            ostatnia_klatka = teraz
            if dt_klatki > 0:
                fps_chwilowy = 1.0 / dt_klatki
                fps = fps_chwilowy if fps == 0 else fps * 0.85 + fps_chwilowy * 0.15
            kl = klawisze()
            if 'Q' in kl:
                siec.aktywna = False
                break
            if 'R' in kl and not siec.aktywna:
                MAPA, cx, cy, dx, dy, sciezka = generuj_tor(ROZMIAR)
                n_sc = len(sciezka)
                boty = utworz_boty(sciezka, preset["konfig"])
                px, py = -dy * 0.72, dx * 0.72
                v = 0.0
                vel_x = 0.0
                vel_y = 0.0
                skr = 0.0
                nitro = 100.0
                boost_pad_do = 0.0
                t0 = time.time()
                z_dala = False
                gracz_lap = 0
                gracz_idx = 0
                start_x, start_y = cx, cy
                time.sleep(0.15)
                continue
            if 'C' in kl:
                if not c_wcisniete:
                    tpp = not tpp
                    c_wcisniete = True
            else:
                c_wcisniete = False
            if 'M' in kl:
                if not m_wcisniete:
                    dzwiek.wlaczony = not dzwiek.wlaczony
                    if dzwiek.wlaczony:
                        dzwiek.start_muzyki()
                        komunikat_hud = "DZWIEK I MUZYKA: WLACZONE"
                    else:
                        dzwiek.stop_muzyki()
                        komunikat_hud = "DZWIEK I MUZYKA: WYCISZONE"
                    komunikat_czas = time.time() + 1.5
                    m_wcisniete = True
            else:
                m_wcisniete = False

            # ====================================================
            # BOOST PAD NA ASFALCIE ('3') - DLA GRACZA
            # ====================================================
            if MAPA[int(cy)][int(cx)] == '3':
                boost_pad_do = time.time() + 1.5
                if time.time() - ostatni_pad_czas > 1.2:
                    nitro = min(100.0, nitro + 25.0)
                    ostatni_pad_czas = time.time()
                    dzwiek.sfx("nitro.wav", 0.3)
                    komunikat_hud = ">>> BOOST PAD! +25% N2O <<<"
                    komunikat_czas = time.time() + 1.4
            pad_aktywny = time.time() < boost_pad_do

            # ====================================================
            # NITRO + BOOST PAD
            # ====================================================
            nitro_akt = (
                'W' in kl and
                'UP' in kl and
                nitro > 2.0
            )
            if nitro_akt:
                nitro = max(0.0, nitro - 0.9)
                akt_max_v = max_v * 1.32
                bonus_przysp = 1.75
                dzwiek.sfx("nitro.wav", 0.65)
            elif pad_aktywny:
                nitro = min(100.0, nitro + 0.22)
                akt_max_v = max_v * 1.26
                bonus_przysp = 1.65
            else:
                nitro = min(100.0, nitro + 0.22)
                akt_max_v = max_v
                bonus_przysp = 1.0

            # ====================================================
            # PRĘDKOŚĆ
            # ====================================================
            ham = 'DOWN' in kl
            drift = (
                ('S' in kl or 'SPACE' in kl)
                and v > 0.12
            )
            if 'UP' in kl or pad_aktywny:
                if 'UP' in kl:
                    dzwiek.sfx("engine.wav", 0.45)
                if v < 0:
                    v = min(0.0, v + 0.008)
                else:
                    v = min(
                        akt_max_v,
                        v + 0.0046 * bonus_przysp *
                        (1.15 - (v / akt_max_v) * 0.7)
                    )
            elif ham:
                if v > 0.004:
                    v = max(0.0, v - 0.0075)
                else:
                    v = max(-0.14, v - 0.003)
            else:
                if v > 0:
                    v = max(0.0, v - 0.0018)
                else:
                    v = min(0.0, v + 0.0022)
            if drift:
                v = max(0.0, v - 0.0025)

            # ====================================================
            # SKRĘCANIE
            # ====================================================
            max_skr = 0.105 if drift else 0.080
            przyrost = 0.026 if drift else 0.019
            if 'LEFT' in kl and 'RIGHT' not in kl:
                skr = max(skr - przyrost, -max_skr)
            elif 'RIGHT' in kl and 'LEFT' not in kl:
                skr = min(skr + przyrost, max_skr)
            else:
                skr = (
                    0.0
                    if abs(skr * 0.6) < 0.004
                    else skr * 0.6
                )
            if abs(v) > 0.005 and skr != 0.0:
                z = 1 if v > 0 else -1
                dx, dy = obroc(dx, dy, skr * z)
                px, py = obroc(px, py, skr * z)

            # ====================================================
            # FIZYKA SAMOCHODU
            # ====================================================
            bazowa_przyczepnosc = 0.07 if drift else 0.28
            przyczepnosc = min(0.45, bazowa_przyczepnosc * sesja["grip_mult"])
            vel_x += (dx * v - vel_x) * przyczepnosc
            vel_y += (dy * v - vel_y) * przyczepnosc

            # ====================================================
            # RUCH BOTÓW AI (Z OBSŁUGĄ BOOST PADÓW '3')
            # ====================================================
            for b in boty:
                if MAPA[int(b['y'])][int(b['x'])] == '3':
                    b['boost_do'] = time.time() + 1.5
                mnoznik_bota = 1.25 if time.time() < b.get('boost_do', 0.0) else 1.0
                tx, ty = sciezka[b['idx']]
                nx_p, ny_p = sciezka[
                    (b['idx'] + 1) % n_sc
                ]
                seg_ang = math.atan2(
                    ny_p - ty,
                    nx_p - tx
                )
                cel_x = tx - math.sin(seg_ang) * b['pas']
                cel_y = ty + math.cos(seg_ang) * b['pas']
                rx_b = cel_x - b['x']
                ry_b = cel_y - b['y']
                dist_b = math.hypot(rx_b, ry_b)
                if dist_b < 4.5:
                    stary_idx = b['idx']
                    b['idx'] = (b['idx'] + 1) % n_sc
                    if b['idx'] < stary_idx:
                        b['lap'] += 1
                else:
                    kx = rx_b / dist_b
                    ky = ry_b / dist_b
                    b['dx'] = b['dx'] * 0.86 + kx * 0.14
                    b['dy'] = b['dy'] * 0.86 + ky * 0.14
                    dl_b = math.hypot(b['dx'], b['dy'])
                    b['dx'] /= dl_b
                    b['dy'] /= dl_b
                    ostry_zakret = abs(
                        kx * b['dy'] - ky * b['dx']
                    )
                    bazowa_v_bota = b['v_baz'] * mnoznik_bota
                    cel_v = (
                        bazowa_v_bota * 0.72
                        if ostry_zakret > 0.35
                        else bazowa_v_bota
                    )
                    b['vx'] += (
                        b['dx'] * cel_v - b['vx']
                    ) * 0.15
                    b['vy'] += (
                        b['dy'] * cel_v - b['vy']
                    ) * 0.15
                bnx = b['x'] + b['vx']
                bny = b['y'] + b['vy']
                if MAPA[int(b['y'])][int(bnx)] != '1':
                    b['x'] = bnx
                else:
                    b['vx'] *= -0.4
                if MAPA[int(bny)][int(b['x'])] != '1':
                    b['y'] = bny
                else:
                    b['vy'] *= -0.4

            # ====================================================
            # KOLIZJE GRACZ <-> BOTY I BOT <-> BOT
            # ====================================================
            R_KOL = 1.55
            for b in boty:
                dx_k = cx - b['x']
                dy_k = cy - b['y']
                d_k = math.hypot(dx_k, dy_k)
                if 0.001 < d_k < R_KOL:
                    nx_k = dx_k / d_k
                    ny_k = dy_k / d_k
                    nachodzenie = (R_KOL - d_k) * 0.52
                    if MAPA[
                        int(cy + ny_k * nachodzenie)
                    ][
                        int(cx + nx_k * nachodzenie)
                    ] != '1':
                        cx += nx_k * nachodzenie
                        cy += ny_k * nachodzenie
                    if MAPA[
                        int(b['y'] - ny_k * nachodzenie)
                    ][
                        int(b['x'] - nx_k * nachodzenie)
                    ] != '1':
                        b['x'] -= nx_k * nachodzenie
                        b['y'] -= ny_k * nachodzenie
                    rvx = vel_x - b['vx']
                    rvy = vel_y - b['vy']
                    vel_along = rvx * nx_k + rvy * ny_k
                    if vel_along < 0:
                        impuls = -1.35 * vel_along * 0.5
                        vel_x += impuls * nx_k
                        vel_y += impuls * ny_k
                        b['vx'] -= impuls * nx_k
                        b['vy'] -= impuls * ny_k
                        dzwiek.sfx("crash.wav", 0.35)
            v = math.hypot(
                vel_x,
                vel_y
            ) * (1 if v >= 0 else -1)

            for i in range(len(boty)):
                for j in range(i + 1, len(boty)):
                    b1, b2 = boty[i], boty[j]
                    dx_k = b1['x'] - b2['x']
                    dy_k = b1['y'] - b2['y']
                    d_k = math.hypot(dx_k, dy_k)
                    if 0.001 < d_k < R_KOL:
                        nx_k = dx_k / d_k
                        ny_k = dy_k / d_k
                        nach = (R_KOL - d_k) * 0.5
                        b1['x'] += nx_k * nach
                        b1['y'] += ny_k * nach
                        b2['x'] -= nx_k * nach
                        b2['y'] -= ny_k * nach

            # ====================================================
            # RUCH GRACZA I ŚLIZGANIE PO BANDACH
            # ====================================================
            nx = cx + vel_x
            ny = cy + vel_y
            kol_x = MAPA[int(cy)][int(nx)] == '1'
            kol_y = MAPA[int(ny)][int(cx)] == '1'
            if not kol_x:
                cx = nx
            if not kol_y:
                cy = ny
            if kol_x or kol_y:
                dzwiek.sfx("crash.wav", 0.4)
                wnx = (
                    -1.0 if vel_x > 0 else 1.0
                ) if kol_x else 0.0
                wny = (
                    -1.0 if vel_y > 0 else 1.0
                ) if kol_y else 0.0
                dl_n = math.hypot(wnx, wny)
                if dl_n > 0:
                    wnx /= dl_n
                    wny /= dl_n
                dot = vel_x * wnx + vel_y * wny
                if dot < 0:
                    vel_x -= 1.15 * dot * wnx
                    vel_y -= 1.15 * dot * wny
                pred_przed = max(
                    math.hypot(vel_x, vel_y),
                    1e-6
                )
                sin_u = min(
                    1.0,
                    abs(dot) / pred_przed
                )
                wsp = 1.0 - (0.35 * sin_u)
                vel_x *= wsp
                vel_y *= wsp
                v = math.hypot(
                    vel_x,
                    vel_y
                ) * (1 if v >= 0 else -1)
                if v > 0.04:
                    kx = vel_x / abs(v)
                    ky = vel_y / abs(v)
                    dx = dx * 0.85 + kx * 0.15
                    dy = dy * 0.85 + ky * 0.15
                    dl_d = math.hypot(dx, dy)
                    dx /= dl_d
                    dy /= dl_d
                    px, py = -dy * 0.72, dx * 0.72

            # ====================================================
            # POZYCJA W WYŚCIGU NA ŻYWO (LEADERBOARD)
            # ====================================================
            nowy_idx = znajdz_indeks_sciezki(cx, cy, sciezka, gracz_idx)
            if gracz_idx > n_sc * 0.8 and nowy_idx < n_sc * 0.2:
                gracz_lap += 1
            elif gracz_idx < n_sc * 0.2 and nowy_idx > n_sc * 0.8:
                gracz_lap = max(0, gracz_lap - 1)
            gracz_idx = nowy_idx
            postep_gracza = gracz_lap * n_sc + gracz_idx
            wszystkie_postepy = [postep_gracza]
            for b in boty:
                wszystkie_postepy.append(b['lap'] * n_sc + b['idx'])
            if siec.aktywna:
                siec.wyslij_pozycje(
                    nick_gracza,
                    cx,
                    cy,
                    sesja["skin_kod"],
                    postep_gracza
                )
                with siec.lock:
                    for g_lan in siec.gracze_zdalni.values():
                        wszystkie_postepy.append(g_lan.get("postep", 0.0))
            wszystkie_postepy.sort(reverse=True)
            pozycja_w_wyscigu = wszystkie_postepy.index(postep_gracza) + 1
            liczba_aut = len(wszystkie_postepy)

            # ====================================================
            # CZAS OKRĄŻENIA I NAGRODY DO BAZY
            # ====================================================
            dyst_start = math.hypot(
                cx - start_x,
                cy - start_y
            )
            if dyst_start > 80.0:
                z_dala = True
            if z_dala and dyst_start < 7.0:
                c = time.time() - t0
                nowy_rek = False
                if rek is None or c < rek:
                    rek = c
                    nowy_rek = True
                if gracz:
                    nagroda = preset["nagroda"]
                    if nowy_rek:
                        baza.wykonaj_update(
                            "UPDATE gracze SET kasa = kasa + ?, rekord_czas = ? WHERE id = ?",
                            (nagroda, rek, gracz["id"])
                        )
                    else:
                        baza.wykonaj_update(
                            "UPDATE gracze SET kasa = kasa + ? WHERE id = ?",
                            (nagroda, gracz["id"])
                        )
                    komunikat_hud = f"+{nagroda}$ ZA OKRAZENIE!"
                else:
                    komunikat_hud = f"OKRAZENIE: {c:.2f}s!"
                komunikat_czas = time.time() + 3.5
                t0 = time.time()
                z_dala = False

            # ====================================================
            # KAMERA
            # ====================================================
            kat_patrz = (
                -0.55
                if 'A' in kl and 'D' not in kl
                else (
                    0.55
                    if 'D' in kl and 'A' not in kl
                    else 0.0
                )
            )
            vdx, vdy = obroc(dx, dy, kat_patrz)
            vpx, vpy = obroc(px, py, kat_patrz)
            camx, camy = cx, cy
            if tpp:
                for i in range(1, 16):
                    tx = cx - vdx * (1.5 * i / 15)
                    ty = cy - vdy * (1.5 * i / 15)
                    if any(
                        MAPA[int(ty + a)][int(tx + b)] == '1'
                        for a in (-0.2, 0, 0.2)
                        for b in (-0.2, 0, 0.2)
                    ):
                        break
                    camx, camy = tx, ty

            # ====================================================
            # INICJALIZACJA EKRANU Z TŁEM
            # ====================================================
            hor = H // 2 - (2 if tpp else 0)
            ekr = [[' '] * W for _ in range(H)]
            kat_kamery = math.atan2(vdy, vdx)
            baza_tla = renderuj_panorame(
                panorama,
                W,
                hor + 1,
                kat_kamery
            )
            for y, wiersz in enumerate(baza_tla):
                ekr[y] = wiersz
            z_buf = [50.0] * W

            # ====================================================
            # RENDEROWANIE PODŁOŻA (Z BOOST PADAMI '3')
            # ====================================================
            puls = int(time.time() * 8) % 2 == 0
            for y in range(hor + 1, H):
                rd = (0.55 * H) / (y - hor)
                stx = rd * (2 * vpx) / W
                sty = rd * (2 * vpy) / W
                fx = camx + rd * (vdx - vpx)
                fy = camy + rd * (vdy - vpy)
                for x in range(W):
                    ifx, ify = int(fx), int(fy)
                    if 0 <= ify < ROZMIAR and 0 <= ifx < ROZMIAR and MAPA[ify][ifx] == '3':
                        ekr[y][x] = f"{CY if puls else BI}^{R}"
                    elif (
                        (0.46 < (fx * 0.5) % 1 < 0.54
                         and ify % 2 == 0)
                        or
                        (0.46 < (fy * 0.5) % 1 < 0.54
                         and ifx % 2 == 0)
                    ):
                        ekr[y][x] = f"{BI}={R}"
                    elif (ifx + ify) % 2 == 0:
                        ekr[y][x] = f"{SZ}.{R}"
                    fx += stx
                    fy += sty

            # ====================================================
            # RAYCASTING ŚCIAN Z TEKSTURĄ TRUECOLOR I MGŁĄ
            # ====================================================
            for x in range(W):
                cp = 2 * x / float(W) - 1
                rx = vdx + vpx * cp
                ry = vdy + vpy * cp
                mx, my = int(camx), int(camy)
                ddx = abs(1 / rx) if rx else 1e30
                ddy = abs(1 / ry) if ry else 1e30
                if rx < 0:
                    sx = -1
                    sdx = (camx - mx) * ddx
                else:
                    sx = 1
                    sdx = (mx + 1.0 - camx) * ddx
                if ry < 0:
                    sy = -1
                    sdy = (camy - my) * ddy
                else:
                    sy = 1
                    sdy = (my + 1.0 - camy) * ddy
                hit = 0
                side = 0
                kroki_ray = 0
                while not hit and kroki_ray < 50:
                    if sdx < sdy:
                        sdx += ddx
                        mx += sx
                        side = 0
                    else:
                        sdy += ddy
                        my += sy
                        side = 1
                    kroki_ray += 1
                    if MAPA[my][mx] in '12':
                        hit = MAPA[my][mx]
                if not hit:
                    continue
                dist = max(
                    (sdx - ddx) if side == 0 else (sdy - ddy),
                    0.1
                )
                z_buf[x] = dist
                de = min(
                    H - 1,
                    int(H / (2 * dist)) + hor
                )
                wys_sciany = max(1, int((H / dist) * 0.42))
                ds_pelne = de - wys_sciany
                ds = max(0, ds_pelne)
                wx = (
                    camy + dist * ry
                    if side == 0
                    else camx + dist * rx
                )
                wx -= math.floor(wx)
                if hit == '2':
                    zb = f"{ZI}#{R}"
                    for y in range(ds, de + 1):
                        ekr[y][x] = zb
                else:
                    tx = int(wx * tex_w) % tex_w
                    mgla = max(0.18, 1.0 - dist / 46.0)
                    if side == 1:
                        mgla *= 0.80
                    for y in range(ds, de + 1):
                        v_gora = ((y - ds_pelne) / float(wys_sciany)) * tex_h
                        v_dol = ((y - ds_pelne + 0.5) / float(wys_sciany)) * tex_h
                        ty1 = min(tex_h - 1, max(0, int(v_gora)))
                        ty2 = min(tex_h - 1, max(0, int(v_dol)))
                        r1, g1, b1 = tex_sciana[ty1][tx]
                        r2, g2, b2 = tex_sciana[ty2][tx]
                        r1 = int(r1 * mgla)
                        g1 = int(g1 * mgla)
                        b1 = int(b1 * mgla)
                        r2 = int(r2 * mgla)
                        g2 = int(g2 * mgla)
                        b2 = int(b2 * mgla)
                        ekr[y][x] = (
                            f"{ESC}[38;2;{r1};{g1};{b1}m"
                            f"{ESC}[48;2;{r2};{g2};{b2}m"
                            f"▀{R}"
                        )

            # ====================================================
            # RENDEROWANIE BOTÓW 3D I GRACZY LAN
            # ====================================================
            wszystkie_auta = list(boty)
            if siec.aktywna:
                with siec.lock:
                    for g_lan in siec.gracze_zdalni.values():
                        _, k_ansi, _ = MAPA_SKINOW.get(
                            g_lan["kol"],
                            MAPA_SKINOW["NI"]
                        )
                        wszystkie_auta.append({
                            "x": g_lan["x"],
                            "y": g_lan["y"],
                            "kol": k_ansi
                        })
            inv_det = 1.0 / (vpx * vdy - vdx * vpy)
            boty_sort = sorted(
                wszystkie_auta,
                key=lambda b: (
                    (b['x'] - camx)**2 +
                    (b['y'] - camy)**2
                ),
                reverse=True
            )
            sprite_auto = [
                "  .=====.  ",
                " |  [ ]  | ",
                "|=========|",
                "|[OO] [OO]|",
                " |_|   |_| ",
            ]
            for b in boty_sort:
                sx_r = b['x'] - camx
                sy_r = b['y'] - camy
                tx_s = inv_det * (
                    vdy * sx_r - vdx * sy_r
                )
                ty_s = inv_det * (
                    -vpy * sx_r + vpx * sy_r
                )
                if ty_s <= 0.6 or ty_s > 45.0:
                    continue
                ekran_x = int(
                    (W / 2) * (1 + tx_s / ty_s)
                )
                wys_s = max(
                    2,
                    int((H / ty_s) * 0.55)
                )
                szer_s = max(
                    3,
                    int((H / ty_s) * 1.15)
                )
                dolek_y = min(
                    H - 1,
                    int(H / (2 * ty_s)) + hor
                )
                gora_y = max(
                    0,
                    dolek_y - wys_s
                )
                lewo_x = ekran_x - szer_s // 2
                for col in range(
                    max(0, lewo_x),
                    min(W, lewo_x + szer_s)
                ):
                    if ty_s < z_buf[col]:
                        u = int(
                            ((col - lewo_x) / float(szer_s)) * 11
                        )
                        u = min(10, max(0, u))
                        for row in range(gora_y, dolek_y + 1):
                            v_s = int(
                                ((row - gora_y) /
                                 float(max(1, dolek_y - gora_y + 1))) * 5
                            )
                            v_s = min(4, max(0, v_s))
                            zn = sprite_auto[v_s][u]
                            if zn != ' ':
                                k_s = (
                                    CZ
                                    if v_s == 3 and zn in 'O[]'
                                    else (
                                        SZ
                                        if v_s == 4
                                        else (
                                            BI
                                            if v_s == 1 and zn in '[]'
                                            else b['kol']
                                        )
                                    )
                                )
                                ekr[row][col] = f"{k_s}{zn}{R}"

            # ====================================================
            # SAMOCHÓD GRACZA
            # ====================================================
            if tpp and kat_patrz == 0.0:
                auto = [
                    "  .============.   ",
                    " |     [  ]     |  ",
                    "|================|",
                    "| [OO]      [OO] |",
                    "|________________|",
                    " |_|          |_|"
                ]
                sw = (
                    -1 if skr < -0.02
                    else (1 if skr > 0.02 else 0)
                )
                sxa = (
                    (W - len(auto[0])) // 2
                    + sw * (5 if drift else 3)
                )
                sya = H - len(auto)
                for ri, w in enumerate(auto):
                    for ci, z in enumerate(w):
                        if (
                            0 <= sxa + ci < W
                            and z != ' '
                        ):
                            kol = (
                                CZ if (ham or drift)
                                else ZO
                            ) if ri == 3 and z in 'O[]' else (
                                SZ if ri == 5
                                else (
                                    BI
                                    if ri == 1 and z in '[]'
                                    else kolor_gracza
                                )
                            )
                            ekr[sya + ri][sxa + ci] = (
                                f"{kol}{z}{R}"
                            )
                if nitro_akt or pad_aktywny:
                    if 0 <= sxa + 5 < W:
                        ekr[H - 1][sxa + 5] = f"{CY}*{R}"
                    if 0 <= sxa + 14 < W:
                        ekr[H - 1][sxa + 14] = f"{CY}*{R}"

            # ====================================================
            # RADAR (Z BOOST PADAMI '+')
            # ====================================================
            rx_r, ry_r = 10, 5
            bot_komorki = {
                (int(b['x']), int(b['y'])): b['kol']
                for b in wszystkie_auta
            }
            for dy_m in range(-ry_r, ry_r + 1):
                for dx_m in range(-rx_r, rx_r + 1):
                    mx = int(cx) + dx_m
                    my = int(cy) + dy_m
                    ex = W - 23 + (dx_m + rx_r)
                    ey = 1 + (dy_m + ry_r)
                    if dx_m == 0 and dy_m == 0:
                        ekr[ey][ex] = f"{ZO}@{R}"
                    elif (mx, my) in bot_komorki:
                        ekr[ey][ex] = (
                            f"{bot_komorki[(mx, my)]}V{R}"
                        )
                    elif (
                        0 <= my < ROZMIAR
                        and 0 <= mx < ROZMIAR
                    ):
                        if MAPA[my][mx] == '1':
                            ekr[ey][ex] = f"{SZ}#{R}"
                        elif MAPA[my][mx] == '2':
                            ekr[ey][ex] = f"{ZI}={R}"
                        elif MAPA[my][mx] == '3':
                            ekr[ey][ex] = f"{CY}+{R}"
                        else:
                            ekr[ey][ex] = ' '
                    else:
                        ekr[ey][ex] = f"{SZ}#{R}"

            # ====================================================
            # POZYCJA W WYŚCIGU (LEWY GÓRNY RÓG) + OSTRZEŻENIA
            # ====================================================
            kol_poz = ZL if pozycja_w_wyscigu == 1 else (
                ZI if pozycja_w_wyscigu <= 3 else BI
            )
            etykieta_poz = f"POZ: {pozycja_w_wyscigu}/{liczba_aut} | OKR: {gracz_lap + 1}"
            for i, ch in enumerate(etykieta_poz):
                if 1 + i < W - 24:
                    ekr[1][1 + i] = f"{kol_poz}{ch}{R}"
            kmh = int(
                math.hypot(vel_x, vel_y) / max_v * 240
            )
            ostr_txt, ostr_kol = sprawdz_zakret(
                MAPA,
                cx,
                cy,
                dx,
                dy,
                kmh
            )
            if time.time() < komunikat_czas:
                ostr_txt = komunikat_hud
                ostr_kol = ZL
            if ostr_txt:
                sx_o = max(
                    1,
                    (W - 24 - len(ostr_txt)) // 2
                )
                for i, ch in enumerate(ostr_txt):
                    if sx_o + i < W - 24:
                        ekr[2][sx_o + i] = (
                            f"{ostr_kol}{ch}{R}"
                        )

            # ====================================================
            # HUD I WYŚWIETLANIE
            # ====================================================
            rt = (
                f"{rek:.2f}s"
                if rek
                else "--.--"
            )
            pasek_n = (
                "█" * int(nitro // 10)
                + "░" * (10 - int(nitro // 10))
            )
            kol_n = CY if (nitro_akt or pad_aktywny) else ZI
            buf = [
                f"{BI}{kmh:3d}km/h | FPS:{fps:5.1f} | "
                f"N2O:{kol_n}{pasek_n}{BI} | "
                f"CZAS:{time.time()-t0:5.1f}s | "
                f"REK:{rt} | "
                f"[Q]Menu [M]Sfx{R}\n"
                + "+" + "-" * W + "+\n"
            ]
            buf.extend(
                "|" + "".join(w) + "|\n"
                for w in ekr
            )
            buf.append(
                "+" + "-" * W + "+\n"
            )
            sys.stdout.write(
                f"{ESC}[H" + "".join(buf)
            )
            sys.stdout.flush()
            time.sleep(0.03)
    finally:
        dzwiek.stop_muzyki()
        sys.stdout.write(
            f"{ESC}[?25h{ESC}[0m\n"
        )
        if os.name != 'nt':
            termios.tcsetattr(
                fd,
                termios.TCSADRAIN,
                st
            )


if __name__ == "__main__":
    baza = BazaDanych()
    while True:
        sesja = menu_glowne(baza)
        gra(baza, sesja)