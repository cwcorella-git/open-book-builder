"""About tab: what the Open Book is, how to order the boards, project status, credits."""
from __future__ import annotations

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

FAB = "https://github.com/joeycastillo/The-Open-Book/tree/main/Fabrication%20Files"
LIBROS = "https://github.com/joeycastillo/libros"

SECTIONS = [
    ("What the Open Book is", f"""
<p>The Open Book is an open-source hardware e-reader designed by <a href="https://joeycastillo.com">Joey Castillo</a>,
licensed <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC-BY-SA 4.0</a>. It pairs a Raspberry Pi Pico with a
4.2-inch black and white e-paper display, runs on two AAA cells and reads books from a microSD card. The firmware
supports bold, italic, chapter breaks, front matter and the Unicode Basic Multilingual Plane, including right-to-left scripts.</p>
<p>The hardware is two boards. The <b>main board (C1, OSO-BOOK-C1)</b> carries the Pico, the battery holder, the buttons,
the microSD socket and the display connection. The <b>driver module (C2, OSO-BOOK-C2)</b> is a small board that solders onto the
main board by its castellated edge. It makes the voltages the display needs and converts signal levels between the Pico and the
panel. You order the driver module already assembled and fit it in one step.</p>"""),
    ("Ordering the boards", f"""
<p>You need a C1 board, a C2 module and a display panel. The files are in the upstream
<a href="{FAB}">Fabrication Files</a> folder. The upstream README names older file versions; the choices below are the ones
this project follows.</p>
<h4>C1 main board, bare PCB</h4>
<ul>
<li>File: <code>OSO-BOOK-C1-05-rounded.zip</code>. It holds Gerber and drill files only. It has no placement file and no
assembly-ready parts list, so a factory cannot assemble the board from it alone. This project prepared both (see
<code>docs/c1-assembly-package.md</code>).</li>
<li>Two copper layers, 1.0 mm thick, lead-free HASL or ENIG, 1 oz copper. Fabricators default to 1.6 mm and leaded HASL, so change both.</li>
<li>The embedded board source is labelled C1-06. Its outline, mounting holes and drills match the C1-05 Gerbers. The Pico's
SMD pads sit 0.9 mm further out in the C1-05 Gerbers than in that source. The Board tab can show either.</li>
</ul>
<h4>C2 driver module, assembled</h4>
<ul>
<li>Route: the <b>C2-03</b> package for JLCPCB (BOM, placement file and Gerbers from one folder). The Board tab reads the C2-03 files. C2-02 and C2-03 list the same
parts and nets and differ only in position and R1's package.</li>
<li>Same board settings as C1: 1.0 mm, lead-free HASL, castellated holes on. Ask the maker to quote assembly, setup,
shipping and tax separately. No quote has been obtained.</li>
</ul>
<h4>Display</h4>
<ul>
<li>The original GDEW042T2 is end of life. The replacement is the <b>GDEY042T81</b> (SSD1683 controller) in the black and white
model, not the tri-colour one.</li>
<li>It is <b>unvalidated</b> on the published C2 design. Good Display's reference circuit uses a 47 µH inductor, a 2.2 Ω sense
resistor and a 1 MΩ pulldown on GDR; the C2 design has 10 µH, 0.47 Ω and no pulldown. See <code>docs/gdey-c2-values-check.md</code>.
Treat the first assembled unit as a pilot.</li>
<li>Firmware: libros needs community PR #10 (fixes a broken Pico build) and PR #11 (chooses the display driver at runtime) for
this panel. Both were open and unmerged on 2026-11-17.</li>
</ul>"""),
    ("What this app does", """
<p>Open Book Builder shows the parts list, the assembly steps, both boards and the case models for the Pico-based Open Book,
and keeps a checklist of what to buy for a batch. It reads the original design files (KiCad for the main board, EAGLE for the
driver module) and does not change them.</p>
<ul>
<li><b>BOM</b>: parts with dated prices, spares, order quantities and a Digi-Key CSV export.</li>
<li><b>Checklist</b>: parts, boards, cards, fees and tools for the first batch, with open items kept open.</li>
<li><b>Assembly</b>: build steps with saved progress. Steps rewritten after the review are marked Untested.</li>
<li><b>Board</b>: a 2D view of each board drawn from the order files, and a 3D view with a box for every part (heights from the footprint tables, not the real part shapes). Parts can be selected in both.</li>
<li><b>Case</b>: the printable case models. Cases are not part of the first batch.</li>
</ul>
<p>The older React and Tauri version, with a 3D board view, lives at the git tag <code>web-tool-final</code>.</p>"""),
    ("Project status, November 2026", f"""
<p>The Pico-based build covered here is the current do-it-yourself version. The <a href="{LIBROS}">libros</a> firmware repository's
last maintainer commit is from 2024-02-02, and four pull requests are open. PR #10 and PR #11, both from
<a href="https://github.com/tahnok">@tahnok</a>, are the two a working Pico build needs with this display
(<a href="{LIBROS}/pull/10">#10</a>, <a href="{LIBROS}/pull/11">#11</a>).</p>
<p>The firmware has been built here with both pull requests (<code>docs/firmware-build-2026-11.md</code>). Nothing has been
flashed or run on a board.</p>
<p>Separately, the designer has announced the
<a href="https://www.crowdsupply.com/oddly-specific-objects/open-book-touch">Open Book Touch</a>, an ESP32-S3 e-reader with a
touch display, front light, wireless and USB-C charging. Its status was last checked in April 2026 and not rechecked.</p>
<p>Community: <a href="https://discord.gg/b6FgeqSZs3">Discord</a>, the
<a href="https://www.oddlyspecificobjects.com/projects/openbook/">project documentation</a> (a 2022 page) and the
<a href="https://hackaday.io/project/192688-the-open-book">Hackaday.io project</a>.</p>"""),
    ("Credits and license", """
<p>The Open Book hardware is by Joey Castillo, licensed CC-BY-SA 4.0. Upstream source:
<a href="https://github.com/joeycastillo/The-Open-Book">github.com/joeycastillo/The-Open-Book</a>.</p>
<p>This app is MIT-licensed and was built with Claude Code. Issues and patches:
<a href="https://github.com/cwcorella-git/open-book-builder">github.com/cwcorella-git/open-book-builder</a>.</p>"""),
    ("For developers", """
<p>Python with PySide6. The dataset is built at every start from the files in <code>data/</code> by the parsers in
<code>src/open_book_builder/build/</code>. Tests run offscreen with <code>uv run pytest</code>. See <code>README.md</code> and
<code>CLAUDE.md</code> in the repository.</p>"""),
]


def about_html() -> str:
    body = "".join(f"<h2>{title}</h2>{html}" for title, html in SECTIONS)
    return f"<html><body>{body}</body></html>"


class AboutTab(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setHtml(about_html())
        layout = QVBoxLayout(self)
        layout.addWidget(self.browser)
