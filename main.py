"""
YT-Video-Téléchargeur v1.3 - Interface PySide6 (fonctionnelle)

- Téléchargement réel via yt-dlp (QThread, progression en direct)
- Pause / Reprise / Annuler / Effacer par téléchargement
- Choix du dossier, collage du lien, import des cookies navigateur
- Icônes Font Awesome (qtawesome)
"""
import os
import sys
import urllib.request

from PySide6.QtCore import Qt, QRectF, QThread, Signal, QObject
from PySide6.QtGui import (
    QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPixmap,
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QMessageBox, QProgressBar, QPushButton, QScrollArea,
    QVBoxLayout, QWidget, QGraphicsDropShadowEffect,
)

import qtawesome as qta

try:
    from yt_dlp import YoutubeDL
    HAS_YTDLP = True
except Exception:
    HAS_YTDLP = False

# ----------------------------------------------------------------------------
# Palette
# ----------------------------------------------------------------------------
RED = "#e02424"
RED_DARK = "#b91c1c"
RED_HOVER = "#f03b3b"
BG = "#0a0a0a"
PANEL = "#141414"
BORDER = "#2a2a2a"
TXT = "#f5f5f5"
TXT_DIM = "#9a9a9a"
GREEN = "#22c55e"

QUALITY_MAP = {"MP4 - 1080p": 1080, "4K": 2160, "720p": 720, "480p": 480}
BROWSERS = ["chrome", "edge", "firefox", "brave", "opera", "vivaldi"]


# ----------------------------------------------------------------------------
# Helpers visuels
# ----------------------------------------------------------------------------
def make_thumbnail(w=112, h=72) -> QPixmap:
    pm = QPixmap(w, h)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), 6, 6)
    p.setClipPath(path)
    grad = QLinearGradient(0, 0, w, h)
    grad.setColorAt(0, QColor("#1e3a5f"))
    grad.setColorAt(1, QColor("#0f2238"))
    p.fillRect(0, 0, w, h, grad)
    p.setPen(QColor("#f5d142"))
    p.setFont(QFont("Arial", 10, QFont.Bold))
    p.drawText(QRectF(6, 6, w * 0.6, h - 12),
               Qt.AlignLeft | Qt.AlignVCenter, "Python\nTraining")
    p.setBrush(QColor("#6b7280"))
    p.setPen(Qt.NoPen)
    p.drawEllipse(QRectF(w * 0.62, h * 0.18, w * 0.22, w * 0.22))
    p.drawRoundedRect(QRectF(w * 0.55, h * 0.55, w * 0.38, h * 0.5), 8, 8)
    p.end()
    return pm


def rounded(pm: QPixmap, w=112, h=72, radius=6) -> QPixmap:
    src = pm.scaled(w, h, Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation)
    out = QPixmap(w, h)
    out.fill(Qt.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, w, h), radius, radius)
    p.setClipPath(path)
    p.drawPixmap((w - src.width()) // 2, (h - src.height()) // 2, src)
    p.end()
    return out


def youtube_icon(size=22) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(RED))
    p.setPen(Qt.NoPen)
    p.drawRoundedRect(QRectF(0, size * 0.18, size, size * 0.64),
                      size * 0.22, size * 0.22)
    tri = QPainterPath()
    cx, cy = size * 0.42, size * 0.5
    tri.moveTo(cx - size * 0.07, cy - size * 0.13)
    tri.lineTo(cx - size * 0.07, cy + size * 0.13)
    tri.lineTo(cx + size * 0.16, cy)
    tri.closeSubpath()
    p.setBrush(QColor("#ffffff"))
    p.drawPath(tri)
    p.end()
    return pm


def glow(widget, color=RED, blur=22, alpha=170):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    c = QColor(color)
    c.setAlpha(alpha)
    eff.setColor(c)
    eff.setOffset(0, 0)
    widget.setGraphicsEffect(eff)


def human_size(n):
    if not n:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


# ----------------------------------------------------------------------------
# Worker de téléchargement
# ----------------------------------------------------------------------------
class DownloadWorker(QThread):
    info_ready = Signal(str, bytes)        # titre, octets miniature
    progress = Signal(dict)                # infos de progression
    finished_ok = Signal(str)              # chemin fichier
    failed = Signal(str)                   # message d'erreur

    def __init__(self, url, outdir, quality, fmt, cookies_browser=None,
                 cookies_file=None):
        super().__init__()
        self.url = url
        self.outdir = outdir
        self.height = QUALITY_MAP.get(quality, 1080)
        self.fmt = fmt.lower()
        self.cookies_browser = cookies_browser
        self.cookies_file = cookies_file
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def _hook(self, d):
        if self._cancel:
            raise RuntimeError("__cancelled__")
        self.progress.emit(d)

    def _opts(self):
        opts = {
            "outtmpl": os.path.join(self.outdir, "%(title)s.%(ext)s"),
            # meilleure vidéo + meilleur audio, plafonnés à la hauteur choisie
            "format": (f"bv*[height<={self.height}]+ba/"
                       f"b[height<={self.height}]/bv*+ba/b"),
            # tri qualité : résolution > fps > codec > bitrate
            "format_sort": [
                "res", "fps", "hdr:12",
                "vcodec:av01:vp9.2:vp9:h265:h264", "acodec", "br",
            ],
            "merge_output_format": self.fmt,
            "progress_hooks": [self._hook],
            "noplaylist": True,
            "continuedl": True,
            "quiet": True,
            "no_warnings": True,
            # --- robustesse contre les HTTP 403 Forbidden ---
            "retries": 10,
            "fragment_retries": 10,
            "retry_sleep_functions": {"http": lambda n: min(2 ** n, 30)},
            "http_headers": {
                "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                               "AppleWebKit/537.36 (KHTML, like Gecko) "
                               "Chrome/124.0.0.0 Safari/537.36"),
            },
        }
        if self.cookies_file:
            opts["cookiefile"] = self.cookies_file
        elif self.cookies_browser:
            opts["cookiesfrombrowser"] = (self.cookies_browser,)
        return opts

    def run(self):
        if not HAS_YTDLP:
            self.failed.emit("yt-dlp n'est pas installé.")
            return
        try:
            os.makedirs(self.outdir, exist_ok=True)
            with YoutubeDL(self._opts()) as ydl:
                info = ydl.extract_info(self.url, download=False)
                title = info.get("title", self.url)
                thumb = b""
                turl = info.get("thumbnail")
                if turl:
                    try:
                        thumb = urllib.request.urlopen(turl, timeout=8).read()
                    except Exception:
                        thumb = b""
                self.info_ready.emit(title, thumb)
                if self._cancel:
                    return
                ydl.download([self.url])
            self.finished_ok.emit(title)
        except Exception as e:
            if self._cancel or "__cancelled__" in str(e):
                return
            self.failed.emit(str(e))


# ----------------------------------------------------------------------------
# Barre de titre
# ----------------------------------------------------------------------------
class TitleBar(QFrame):
    def __init__(self, parent):
        super().__init__(parent)
        self._win = parent
        self._drag = None
        self.setFixedHeight(38)
        self.setObjectName("titlebar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 6, 0)
        lay.setSpacing(8)

        icon = QLabel()
        icon.setPixmap(youtube_icon(20))
        lay.addWidget(icon)
        title = QLabel("YT-Video-Téléchargeur v1.3")
        title.setObjectName("titletext")
        lay.addWidget(title)
        lay.addStretch()

        for ic, obj, slot in (
            ("fa5s.minus", "wbtn", self._win.showMinimized),
            ("fa5.window-maximize", "wbtn", self._toggle_max),
            ("fa5s.times", "wbtn_close", self._win.close),
        ):
            b = QPushButton()
            b.setIcon(qta.icon(ic, color="#cfcfcf"))
            b.setObjectName(obj)
            b.setFixedSize(38, 26)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            lay.addWidget(b)

    def _toggle_max(self):
        self._win.showNormal() if self._win.isMaximized() else self._win.showMaximized()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self._win.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self._win.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        self._toggle_max()


# ----------------------------------------------------------------------------
# Élément de téléchargement
# ----------------------------------------------------------------------------
class DownloadItem(QFrame):
    pause_clicked = Signal()
    cancel_clicked = Signal()
    clear_clicked = Signal()

    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("dlitem")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(6)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.thumb = QLabel()
        self.thumb.setPixmap(make_thumbnail())
        self.thumb.setFixedSize(112, 72)
        top.addWidget(self.thumb, 0, Qt.AlignTop)

        info = QVBoxLayout()
        info.setSpacing(2)
        self.title = QLabel(title)
        self.title.setObjectName("dltitle")
        self.title.setWordWrap(True)
        info.addWidget(self.title)
        self.meta = QLabel("Initialisation...")
        self.meta.setObjectName("dlinfo")
        info.addWidget(self.meta)
        self.status = QLabel("")
        self.status.setObjectName("pending")
        info.addWidget(self.status)
        info.addStretch()
        top.addLayout(info, 1)

        ctr = QHBoxLayout()
        ctr.setSpacing(6)
        self.btn_pause = self._ctrl("fa5s.pause", "Pause", self.pause_clicked)
        self.btn_cancel = self._ctrl("fa5s.times", "Annuler", self.cancel_clicked)
        self.btn_clear = self._ctrl("fa5s.trash", "Effacer", self.clear_clicked)
        for b in (self.btn_pause, self.btn_cancel, self.btn_clear):
            ctr.addWidget(b)
        top.addLayout(ctr, 0)
        outer.addLayout(top)

        prow = QHBoxLayout()
        self.prog_left = QLabel("")
        self.prog_left.setObjectName("dlinfo")
        self.prog_right = QLabel("0%")
        self.prog_right.setObjectName("dlpercent")
        prow.addWidget(self.prog_left)
        prow.addStretch()
        prow.addWidget(self.prog_right)
        outer.addLayout(prow)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        outer.addWidget(self.bar)

    def _ctrl(self, icon, label, signal):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(3)
        b = QPushButton()
        b.setIcon(qta.icon(icon, color="white"))
        b.setObjectName("ctrlbtn")
        b.setFixedSize(42, 34)
        b.setCursor(Qt.PointingHandCursor)
        b.clicked.connect(signal.emit)
        v.addWidget(b, 0, Qt.AlignCenter)
        l = QLabel(label)
        l.setObjectName("ctrllbl")
        l.setAlignment(Qt.AlignCenter)
        v.addWidget(l)
        w._btn = b
        w._lbl = l
        return w

    # ---- mises à jour d'état ----
    def set_thumb_bytes(self, data: bytes):
        if not data:
            return
        pm = QPixmap()
        if pm.loadFromData(data):
            self.thumb.setPixmap(rounded(pm))

    def update_progress(self, d):
        st = d.get("status")
        if st == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes", 0)
            speed = d.get("speed") or 0
            pct = int(done / total * 100) if total else 0
            self.bar.setValue(pct)
            self.prog_right.setText(f"{pct}%")
            self.prog_left.setText(
                f"{human_size(done)} / {human_size(total)} | "
                f"{human_size(speed)}/s")
            self.status.setText("")
        elif st == "finished":
            self.bar.setValue(100)
            self.prog_right.setText("100%")
            self.meta.setText("Fusion / conversion...")

    def set_done(self):
        self.bar.setValue(100)
        self.prog_right.setText("100%")
        self.status.setObjectName("done")
        self.status.setText("\u2713 Terminé")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        self.btn_pause._btn.setEnabled(False)
        self.btn_cancel._btn.setEnabled(False)

    def set_error(self, msg):
        self.status.setObjectName("errlbl")
        self.status.setText("Erreur")
        self.status.setToolTip(msg)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def set_paused(self, paused):
        if paused:
            self.btn_pause._btn.setIcon(qta.icon("fa5s.play", color="white"))
            self.btn_pause._lbl.setText("Reprendre")
            self.status.setText("En pause")
        else:
            self.btn_pause._btn.setIcon(qta.icon("fa5s.pause", color="white"))
            self.btn_pause._lbl.setText("Pause")
            self.status.setText("")

    def set_cancelled(self):
        self.status.setText("Annulé")
        self.btn_pause._btn.setEnabled(False)
        self.btn_cancel._btn.setEnabled(False)


# ----------------------------------------------------------------------------
# Fenêtre principale
# ----------------------------------------------------------------------------
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(530, 650)
        self.resize(560, 650)

        self.cookies_browser = None
        self.cookies_file = None
        self.jobs = {}   # item -> {"worker","url","outdir","quality","fmt","paused"}

        self.root = QFrame()
        self.root.setObjectName("root")
        glow(self.root, RED, blur=38, alpha=110)
        shell = QVBoxLayout(self)
        shell.setContentsMargins(14, 14, 14, 14)
        shell.addWidget(self.root)

        v = QVBoxLayout(self.root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(TitleBar(self))

        body = QVBoxLayout()
        body.setContentsMargins(16, 12, 16, 14)
        body.setSpacing(7)
        v.addLayout(body)
        self._build_body(body)
        self.setStyleSheet(STYLE)

    def _label(self, text):
        l = QLabel(text)
        l.setObjectName("section")
        return l

    def _build_body(self, body):
        # lien
        body.addWidget(self._label("Coller le lien de la vidéo YouTube :"))
        row = QHBoxLayout()
        row.setSpacing(8)
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://www.youtube.com/watch?v=...")
        self.url.setObjectName("input")
        self.url.setFixedHeight(42)
        row.addWidget(self.url, 1)
        paste = QPushButton("  Coller")
        paste.setIcon(qta.icon("fa5s.paste", color="white"))
        paste.setObjectName("redbtn")
        paste.setFixedHeight(42)
        paste.setCursor(Qt.PointingHandCursor)
        paste.clicked.connect(self._paste)
        row.addWidget(paste)
        body.addLayout(row)

        # chemin
        body.addWidget(self._label("Chemin d'enregistrement :"))
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        browse = QPushButton("  Parcourir")
        browse.setIcon(qta.icon("fa5s.folder-open", color="white"))
        browse.setObjectName("redbtn")
        browse.setFixedHeight(42)
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._browse)
        row2.addWidget(browse)
        default_dir = os.path.join(os.path.expanduser("~"), "Videos", "Downloads")
        self.path = QLineEdit(default_dir)
        self.path.setObjectName("pathfield")
        self.path.setReadOnly(True)
        self.path.setFixedHeight(42)
        row2.addWidget(self.path, 1)
        body.addLayout(row2)

        # qualité / format / cookies
        labels = QHBoxLayout()
        labels.addWidget(self._label("Sélectionner la Qualité :"))
        labels.addWidget(self._label("Sélectionner le Format :"))
        labels.addStretch()
        body.addLayout(labels)

        row3 = QHBoxLayout()
        row3.setSpacing(8)
        self.quality = QComboBox()
        self.quality.addItems(list(QUALITY_MAP.keys()))
        self.quality.setObjectName("combo")
        self.quality.setFixedHeight(42)
        row3.addWidget(self.quality, 1)
        self.fmt = QComboBox()
        self.fmt.addItems(["MP4", "MKV", "AVI", "FLV"])
        self.fmt.setObjectName("combo")
        self.fmt.setFixedHeight(42)
        row3.addWidget(self.fmt, 1)

        self.cookies = QPushButton("  Cookies")
        self.cookies.setIcon(qta.icon("fa5s.cookie-bite", color="white"))
        self.cookies.setObjectName("cookies")
        self.cookies.setCursor(Qt.PointingHandCursor)
        self.cookies.setFixedSize(120, 42)
        self.cookies.setToolTip("Importer les cookies du navigateur "
                                "(vidéos protégées/restreintes)")
        self.cookies.clicked.connect(self._cookies_menu)
        row3.addWidget(self.cookies, 0)
        body.addLayout(row3)

        # liste
        scroll = QScrollArea()
        scroll.setObjectName("scroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list_container = QWidget()
        self.list_container.setObjectName("listpanel")
        self.clay = QVBoxLayout(self.list_container)
        self.clay.setContentsMargins(8, 8, 8, 8)
        self.clay.setSpacing(6)
        self.empty = QLabel("Aucun téléchargement.\nColle un lien puis clique sur TÉLÉCHARGER.")
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.clay.addWidget(self.empty)
        self.clay.addStretch()
        scroll.setWidget(self.list_container)
        body.addWidget(scroll, 1)

        # télécharger
        bottom = QHBoxLayout()
        bottom.setSpacing(10)
        self.dl_btn = QPushButton("   TÉLÉCHARGER")
        self.dl_btn.setIcon(qta.icon("fa5s.download", color="white"))
        self.dl_btn.setObjectName("download")
        self.dl_btn.setCursor(Qt.PointingHandCursor)
        self.dl_btn.setFixedHeight(74)
        glow(self.dl_btn, RED, blur=26, alpha=140)
        self.dl_btn.clicked.connect(self._start_download)
        bottom.addWidget(self.dl_btn, 1)
        spark = QPushButton()
        spark.setIcon(qta.icon("fa5s.magic", color="#9a9a9a"))
        spark.setObjectName("spark")
        spark.setCursor(Qt.PointingHandCursor)
        spark.setFixedSize(54, 54)
        bottom.addWidget(spark)
        body.addLayout(bottom)

    # ---------------- actions ----------------
    def _paste(self):
        self.url.setText(QApplication.clipboard().text().strip())

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choisir le dossier",
                                             self.path.text())
        if d:
            self.path.setText(d)

    def _cookies_menu(self):
        menu = QMenu(self)
        file_act = menu.addAction(qta.icon("fa5s.file-import", color=TXT),
                                  "Importer un fichier cookies (.txt)...")
        none_act = menu.addAction("Aucun (désactiver)")
        menu.addSeparator()
        sub = menu.addMenu("Depuis un navigateur")
        acts = {sub.addAction(b.capitalize()): b for b in BROWSERS}
        chosen = menu.exec(self.cookies.mapToGlobal(self.cookies.rect().bottomLeft()))
        if chosen is None:
            return
        if chosen is file_act:
            path, _ = QFileDialog.getOpenFileName(
                self, "Choisir un fichier cookies",
                os.path.expanduser("~"),
                "Cookies (*.txt);;Tous les fichiers (*.*)")
            if path:
                self.cookies_file = path
                self.cookies_browser = None
                self.cookies.setText("  Fichier")
                self.cookies.setToolTip(f"Cookies : {path}")
        elif chosen is none_act:
            self.cookies_browser = None
            self.cookies_file = None
            self.cookies.setText("  Cookies")
            self.cookies.setToolTip("Importer les cookies (vidéos protégées)")
        else:
            self.cookies_browser = acts[chosen]
            self.cookies_file = None
            self.cookies.setText(f"  {self.cookies_browser.capitalize()}")
            self.cookies.setToolTip(f"Cookies depuis {self.cookies_browser}")

    def _start_download(self):
        url = self.url.text().strip()
        if not url:
            QMessageBox.warning(self, "Lien manquant",
                                "Colle d'abord un lien YouTube.")
            return
        if not HAS_YTDLP:
            QMessageBox.critical(self, "yt-dlp manquant",
                                 "Installe yt-dlp :  pip install yt-dlp")
            return
        if self.empty.isVisible():
            self.empty.hide()

        item = DownloadItem("Chargement du lien...")
        self.clay.insertWidget(0, item)
        job = {"url": url, "outdir": self.path.text(),
               "quality": self.quality.currentText(),
               "fmt": self.fmt.currentText(), "paused": False, "worker": None}
        self.jobs[item] = job
        item.pause_clicked.connect(lambda it=item: self._toggle_pause(it))
        item.cancel_clicked.connect(lambda it=item: self._cancel(it))
        item.clear_clicked.connect(lambda it=item: self._clear(it))
        self._launch_worker(item)
        self.url.clear()

    def _launch_worker(self, item):
        job = self.jobs[item]
        worker = DownloadWorker(job["url"], job["outdir"], job["quality"],
                                job["fmt"], self.cookies_browser,
                                self.cookies_file)
        job["worker"] = worker
        worker.info_ready.connect(lambda t, b, it=item: self._on_info(it, t, b))
        worker.progress.connect(item.update_progress)
        worker.finished_ok.connect(lambda t, it=item: self._on_done(it))
        worker.failed.connect(lambda m, it=item: item.set_error(m))
        worker.start()

    def _on_info(self, item, title, thumb):
        item.title.setText(title)
        item.meta.setText(f"{self.jobs[item]['quality']} - "
                          f"{self.jobs[item]['fmt']}")
        item.set_thumb_bytes(thumb)

    def _on_done(self, item):
        item.set_done()
        item.meta.setText(self.jobs[item]["outdir"])

    def _toggle_pause(self, item):
        job = self.jobs.get(item)
        if not job:
            return
        if not job["paused"]:
            if job["worker"]:
                job["worker"].cancel()
            job["paused"] = True
            item.set_paused(True)
        else:
            job["paused"] = False
            item.set_paused(False)
            self._launch_worker(item)   # reprend le fichier .part

    def _cancel(self, item):
        job = self.jobs.get(item)
        if job and job["worker"]:
            job["worker"].cancel()
        item.set_cancelled()

    def _clear(self, item):
        job = self.jobs.pop(item, None)
        if job and job["worker"]:
            job["worker"].cancel()
        item.setParent(None)
        item.deleteLater()
        if not self.jobs:
            self.empty.show()


# ----------------------------------------------------------------------------
# Style
# ----------------------------------------------------------------------------
STYLE = f"""
#root {{ background: {BG}; border: 1px solid {RED}; border-radius: 14px; }}
#titlebar {{ background: transparent; border-bottom: 1px solid {RED_DARK};
    border-top-left-radius: 14px; border-top-right-radius: 14px; }}
#titletext {{ color: {TXT}; font-size: 13px; font-weight: 600; }}
#wbtn, #wbtn_close {{ background: transparent; border: none; border-radius: 6px; }}
#wbtn:hover {{ background: #262626; }}
#wbtn_close:hover {{ background: {RED}; }}

QWidget {{ font-family: 'Segoe UI', Arial; color: {TXT}; }}
#section {{ color: {TXT}; font-size: 13px; font-weight: 600; }}

#input, #pathfield {{ background: #101010; border: 1px solid {RED_DARK};
    border-radius: 8px; padding: 0 12px; color: {TXT}; font-size: 13px; }}
#input:focus {{ border: 1px solid {RED}; }}
#pathfield {{ color: {TXT_DIM}; }}

#redbtn {{ background: {RED}; color: white; border: none; border-radius: 8px;
    padding: 0 14px; font-size: 13px; font-weight: 600; }}
#redbtn:hover {{ background: {RED_HOVER}; }}
#redbtn:pressed {{ background: {RED_DARK}; }}

#combo {{ background: #101010; border: 1px solid {RED_DARK}; border-radius: 8px;
    padding: 0 12px; color: {TXT}; font-size: 13px; }}
#combo:hover {{ border: 1px solid {RED}; }}
#combo::drop-down {{ border: none; width: 26px; }}
#combo QAbstractItemView {{ background: #161616; border: 1px solid {RED_DARK};
    selection-background-color: {RED}; color: {TXT}; outline: none; }}

#cookies {{ background: {RED}; color: white; border: none; border-radius: 8px;
    font-size: 12px; font-weight: 700; }}
#cookies:hover {{ background: {RED_HOVER}; }}

#scroll {{ border: none; background: transparent; }}
#listpanel {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 10px; }}
#empty {{ color: {TXT_DIM}; font-size: 13px; padding: 30px; }}

#dlitem {{ background: transparent; border: none; border-bottom: 1px solid {BORDER}; }}
#dltitle {{ color: {TXT}; font-size: 13px; font-weight: 600; }}
#dlinfo {{ color: {TXT_DIM}; font-size: 12px; }}
#dlpercent {{ color: {TXT}; font-size: 13px; font-weight: 700; }}
#done {{ color: {GREEN}; font-size: 13px; font-weight: 600; }}
#pending {{ color: {TXT_DIM}; font-size: 12px; }}
#errlbl {{ color: {RED_HOVER}; font-size: 12px; font-weight: 600; }}

#ctrlbtn {{ background: {RED}; color: white; border: none; border-radius: 8px; }}
#ctrlbtn:hover {{ background: {RED_HOVER}; }}
#ctrlbtn:disabled {{ background: #3a2424; }}
#ctrllbl {{ color: {TXT_DIM}; font-size: 11px; }}

QProgressBar {{ background: #2a0d0d; border: none; border-radius: 4px; }}
QProgressBar::chunk {{ background: {RED}; border-radius: 4px; }}

#download {{ background: {RED}; color: white; border: none; border-radius: 12px;
    font-size: 19px; font-weight: 800; }}
#download:hover {{ background: {RED_HOVER}; }}
#download:pressed {{ background: {RED_DARK}; }}
#spark {{ background: #1a1a1a; border: 1px solid {BORDER}; border-radius: 12px; }}
#spark:hover {{ border: 1px solid {RED}; }}

QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #3a3a3a; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {RED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
"""


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("YT-Video-Téléchargeur")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
