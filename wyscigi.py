import os, sys, time, math, random

from PIL import Image, ImageFile

ESC = chr(27)

if os.name == "nt":
    os.system("")

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
            (0x51, 'Q'), (0x52, 'R')
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
# USTAWIENIA EKRANU I TŁA
# ============================================================

W, H = 80, 24

PLIK_TLA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "background.png")

R, CZ, ZO, SZ, ZI, BI, NI, CY, FI = (
    f"{ESC}[0m",
    f"{ESC}[91m",
    f"{ESC}[93m",
    f"{ESC}[90m",
    f"{ESC}[92m",
    f"{ESC}[97m",
    f"{ESC}[94m",
    f"{ESC}[96m",
    f"{ESC}[95m"
)

ImageFile.LOAD_TRUNCATED_IMAGES = True

# Panorama equirectangular 360° musi mieć proporcje 2:1.
# Środek obrazu (50% szerokości) jest kierunkiem patrzenia na wprost.
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

            # Modulo zapewnia ciągłość panoramy na lewej i prawej krawędzi.
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
# GENEROWANIE TORU
# ============================================================

def generuj_tor(rozmiar=512):

    pedzel = [
        (dx, dy)
        for dy in range(-3, 4)
        for dx in range(-3, 4)
        if dx*dx + dy*dy <= 9
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


def utworz_boty(sciezka):

    boty = []

    konfig = [
        (3, 0.34, -1.1, CZ),
        (6, 0.38, 1.1, ZO),
        (9, 0.41, 0.0, FI),
    ]

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
            'v_baz': v_baz,
            'pas': pas,
            'kol': kol
        })

    return boty


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

def gra():

    ROZMIAR = 512

    MAPA, cx, cy, dx, dy, sciezka = generuj_tor(ROZMIAR)

    boty = utworz_boty(sciezka)

    px, py = -dy * 0.72, dx * 0.72

    v = 0.0
    max_v = 0.46
    skr = 0.0

    t0 = time.time()
    rek = None

    # Pomiar FPS: wygładzona średnia z czasu między klatkami.
    ostatnia_klatka = time.perf_counter()
    fps = 0.0
    z_dala = False

    vel_x, vel_y = 0.0, 0.0

    nitro = 100.0
    tpp = True
    c_wcisniete = False

    start_x, start_y = cx, cy

    # Wczytanie panoramy 360° tylko raz, przed pętlą gry.
    panorama = zaladuj_panorame(PLIK_TLA)

    sys.stdout.write(f"{ESC}[?25l{ESC}[2J")

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
                break

            if 'R' in kl:

                MAPA, cx, cy, dx, dy, sciezka = generuj_tor(ROZMIAR)

                boty = utworz_boty(sciezka)

                px, py = -dy * 0.72, dx * 0.72

                v = 0.0
                vel_x = 0.0
                vel_y = 0.0
                skr = 0.0
                nitro = 100.0

                t0 = time.time()
                rek = None
                z_dala = False

                start_x, start_y = cx, cy

                time.sleep(0.15)
                continue

            if 'C' in kl:

                if not c_wcisniete:
                    tpp = not tpp
                    c_wcisniete = True

            else:
                c_wcisniete = False

            # ====================================================
            # NITRO
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

            if 'UP' in kl:

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

            przyczepnosc = 0.07 if drift else 0.28

            vel_x += (dx * v - vel_x) * przyczepnosc
            vel_y += (dy * v - vel_y) * przyczepnosc

            # ====================================================
            # RUCH BOTÓW AI
            # ====================================================

            n_sc = len(sciezka)

            for b in boty:

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

                    b['idx'] = (b['idx'] + 1) % n_sc

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

                    cel_v = (
                        b['v_baz'] * 0.72
                        if ostry_zakret > 0.35
                        else b['v_baz']
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
            # CZAS OKRĄŻENIA
            # ====================================================

            dyst_start = math.hypot(
                cx - start_x,
                cy - start_y
            )

            if dyst_start > 80.0:
                z_dala = True

            if z_dala and dyst_start < 7.0:

                c = time.time() - t0

                if rek is None or c < rek:
                    rek = c

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

            # Panorama obraca się razem z kierunkiem patrzenia kamery.
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
            # RENDEROWANIE PODŁOŻA
            # ====================================================

            for y in range(hor + 1, H):

                rd = (0.55 * H) / (y - hor)

                stx = rd * (2 * vpx) / W
                sty = rd * (2 * vpy) / W

                fx = camx + rd * (vdx - vpx)
                fy = camy + rd * (vdy - vpy)

                for x in range(W):

                    if (
                        (0.46 < (fx * 0.5) % 1 < 0.54
                         and int(fy) % 2 == 0)
                        or
                        (0.46 < (fy * 0.5) % 1 < 0.54
                         and int(fx) % 2 == 0)
                    ):

                        ekr[y][x] = f"{BI}={R}"

                    elif (int(fx) + int(fy)) % 2 == 0:

                        ekr[y][x] = f"{SZ}.{R}"

                    fx += stx
                    fy += sty

            # ====================================================
            # RAYCASTING ŚCIAN
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

                ds = max(
                    0,
                    de - int((H / dist) * 0.42)
                )

                wx = (
                    camy + dist * ry
                    if side == 0
                    else camx + dist * rx
                )

                if hit == '2':
                    zb = f"{ZI}#{R}"

                elif dist > 30:
                    zb = f"{SZ}░{R}"

                elif dist > 18:
                    zb = f"{SZ}▒{R}"

                else:
                    zb = (
                        f"{CZ if int(wx*2)%2==0 else BI}"
                        f"{'█' if dist < 10 else '▓'}{R}"
                    )

                for y in range(ds, de + 1):
                    ekr[y][x] = zb

            # ====================================================
            # RENDEROWANIE BOTÓW 3D
            # ====================================================

            inv_det = 1.0 / (vpx * vdy - vdx * vpy)

            boty_sort = sorted(
                boty,
                key=lambda b: (
                    (b['x'] - camx)**2 +
                    (b['y'] - camy)**2
                ),
                reverse=True
            )

            sprite_auto = [
                "  .=====.  ",
                " /_[___]_\ ",
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
                                            if v_s == 1 and zn in '[]_'
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
                    "    .===========.   ",
                    "   /  [_______]  \  ",
                    "__|===============|__",
                    "| [OO]         [OO] |",
                    "|___________________|",
                    " |__|           |__|"
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
                                    if ri == 1 and z in '[]_'
                                    else NI
                                )
                            )

                            ekr[sya + ri][sxa + ci] = (
                                f"{kol}{z}{R}"
                            )

                if nitro_akt:

                    if 0 <= sxa + 5 < W:
                        ekr[H - 1][sxa + 5] = f"{CY}*{R}"

                    if 0 <= sxa + 14 < W:
                        ekr[H - 1][sxa + 14] = f"{CY}*{R}"

            # ====================================================
            # RADAR
            # ====================================================

            rx_r, ry_r = 10, 5

            bot_komorki = {
                (int(b['x']), int(b['y'])): b['kol']
                for b in boty
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

                        else:
                            ekr[ey][ex] = ' '

                    else:
                        ekr[ey][ex] = f"{SZ}#{R}"

            # ====================================================
            # OSTRZEŻENIA O ZAKRĘTACH
            # ====================================================

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

            kol_n = CY if nitro_akt else ZI

            buf = [
                f"{BI}{kmh:3d}km/h | FPS:{fps:5.1f} | "
                f"N2O:{kol_n}{pasek_n}{BI} | "
                f"CZAS:{time.time()-t0:5.1f}s | "
                f"REK:{rt} | "
                f"[Strz] [W]N2O [S]Drift [A/D]Patrz [C]Kam{R}\n"
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
    gra()