#!/usr/bin/env python3
"""
gui.py — Minimal Tkinter front-end for ForensicRecover.

The GUI does no carving of its own. It calls the same functions as the CLI:
  carver.carve_image, carver.sha256_file, report.write_reports, erasure.demo_erase
"""

from __future__ import annotations

import sys
import threading
import webbrowser
from pathlib import Path

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError as exc:
    version = sys.version.split()[0]
    print(
        "Tkinter is not available in this Python interpreter.\n"
        f"  {sys.executable} ({version})\n\n"
        "On macOS with Homebrew Python 3.14:\n"
        "  brew install python-tk@3.14\n\n"
        "Then re-run: python3 gui.py",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc

from carver import TOOL_NAME, TOOL_VERSION, carve_image, sha256_file, count_by_type
from report import write_reports
from erasure import demo_erase


APP_BG = "#0f1419"
CARD_BG = "#1a2332"
INK = "#e8eef7"
MUTED = "#93a1b5"
ACCENT = "#3d9cf0"
BTN_BG = "#1f4b78"
BTN_FG = "#ffffff"


class ForensicRecoverApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{TOOL_NAME}  ·  {TOOL_VERSION}")
        self.geometry("980x640")
        self.minsize(860, 560)
        self.configure(bg=APP_BG)

        self.image_path = tk.StringVar()
        self.out_dir = tk.StringVar()
        self.status = tk.StringVar(value="Ready. Select a raw image and an output folder.")
        self.hash_text = tk.StringVar(value="SHA-256: (not computed yet)")
        self.summary_text = tk.StringVar(value="Recovered: —")
        self.report_path: Path | None = None
        self.html_path: Path | None = None
        self._busy = False

        self._build_style()
        self._build_layout()

    # ------------------------------------------------------------------ UI
    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook", background=APP_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=CARD_BG, foreground=INK, padding=(14, 6))
        style.map("TNotebook.Tab", background=[("selected", "#24344c")])
        style.configure("Treeview", background=CARD_BG, fieldbackground=CARD_BG, foreground=INK, rowheight=24)
        style.configure("Treeview.Heading", background="#24344c", foreground=INK)
        style.configure("TFrame", background=APP_BG)
        style.configure("Card.TFrame", background=CARD_BG)
        style.configure("TLabel", background=APP_BG, foreground=INK)
        style.configure("Muted.TLabel", background=APP_BG, foreground=MUTED)
        style.configure("Card.TLabel", background=CARD_BG, foreground=INK)
        style.configure("TButton", padding=6)

    def _build_layout(self) -> None:
        header = tk.Frame(self, bg=APP_BG)
        header.pack(fill="x", padx=18, pady=(16, 8))
        tk.Label(
            header,
            text=TOOL_NAME,
            bg=APP_BG,
            fg=INK,
            font=("Helvetica", 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Advanced file recovery (signature carving) + demo secure erasure",
            bg=APP_BG,
            fg=MUTED,
            font=("Helvetica", 12),
        ).pack(anchor="w")

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=18, pady=8)

        recovery = ttk.Frame(notebook)
        erasure = ttk.Frame(notebook)
        notebook.add(recovery, text="  File Recovery  ")
        notebook.add(erasure, text="  Secure Erasure (Demo)  ")

        self._build_recovery_tab(recovery)
        self._build_erasure_tab(erasure)

        footer = tk.Frame(self, bg=APP_BG)
        footer.pack(fill="x", padx=18, pady=(0, 12))
        tk.Label(
            footer,
            text="Evidence is opened read-only. Prototype for SIH 2026 — not a certified forensic tool.",
            bg=APP_BG,
            fg=MUTED,
            font=("Helvetica", 10),
        ).pack(anchor="w")

    def _build_recovery_tab(self, parent: ttk.Frame) -> None:
        pad = {"padx": 12, "pady": 6}

        row1 = tk.Frame(parent, bg=APP_BG)
        row1.pack(fill="x", **pad)
        tk.Label(row1, text="Forensic image", bg=APP_BG, fg=INK, width=16, anchor="w").pack(side="left")
        tk.Entry(row1, textvariable=self.image_path, bg=CARD_BG, fg=INK, insertbackground=INK).pack(
            side="left", fill="x", expand=True, padx=6
        )
        tk.Button(row1, text="Browse…", command=self._pick_image, bg=BTN_BG, fg=BTN_FG).pack(side="left")

        row2 = tk.Frame(parent, bg=APP_BG)
        row2.pack(fill="x", **pad)
        tk.Label(row2, text="Output folder", bg=APP_BG, fg=INK, width=16, anchor="w").pack(side="left")
        tk.Entry(row2, textvariable=self.out_dir, bg=CARD_BG, fg=INK, insertbackground=INK).pack(
            side="left", fill="x", expand=True, padx=6
        )
        tk.Button(row2, text="Browse…", command=self._pick_out, bg=BTN_BG, fg=BTN_FG).pack(side="left")

        actions = tk.Frame(parent, bg=APP_BG)
        actions.pack(fill="x", **pad)
        tk.Button(
            actions, text="Compute image hash", command=self._hash_only, bg="#2a3b52", fg=BTN_FG
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            actions, text="Start Recovery", command=self._start_recovery, bg=ACCENT, fg="#081018"
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            actions, text="Open HTML report", command=self._open_html, bg="#2a3b52", fg=BTN_FG
        ).pack(side="left")

        tk.Label(parent, textvariable=self.hash_text, bg=APP_BG, fg=MUTED, font=("Menlo", 11)).pack(
            anchor="w", padx=12
        )
        tk.Label(parent, textvariable=self.status, bg=APP_BG, fg=ACCENT, font=("Helvetica", 12)).pack(
            anchor="w", padx=12, pady=(4, 0)
        )
        tk.Label(parent, textvariable=self.summary_text, bg=APP_BG, fg=INK, font=("Helvetica", 12, "bold")).pack(
            anchor="w", padx=12, pady=(0, 6)
        )

        columns = ("filename", "type", "start", "size", "confidence")
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=12)
        for col, label, width in (
            ("filename", "Recovered file", 280),
            ("type", "Type", 80),
            ("start", "Start offset", 140),
            ("size", "Size", 100),
            ("confidence", "Confidence", 110),
        ):
            tree.heading(col, text=label)
            tree.column(col, width=width, anchor="w")
        tree.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.tree = tree

    def _build_erasure_tab(self, parent: ttk.Frame) -> None:
        self.erase_src = tk.StringVar()
        self.erase_method = tk.StringVar(value="clear")
        self.erase_log = tk.Text(
            parent, height=16, bg=CARD_BG, fg=INK, insertbackground=INK, wrap="word", font=("Menlo", 11)
        )

        warn = tk.Label(
            parent,
            text=(
                "DEMO ONLY. This overwrites a COPY of a regular file, never a disk and never the original. "
                "It illustrates NIST SP 800-88 Clear/Purge ideas for the pitch — it is not a certified wiper."
            ),
            bg=APP_BG,
            fg="#f0c14d",
            wraplength=860,
            justify="left",
        )
        warn.pack(anchor="w", padx=12, pady=10)

        row = tk.Frame(parent, bg=APP_BG)
        row.pack(fill="x", padx=12, pady=6)
        tk.Label(row, text="File to sanitize (copy)", bg=APP_BG, fg=INK, width=22, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=self.erase_src, bg=CARD_BG, fg=INK, insertbackground=INK).pack(
            side="left", fill="x", expand=True, padx=6
        )
        tk.Button(row, text="Browse…", command=self._pick_erase_file, bg=BTN_BG, fg=BTN_FG).pack(side="left")

        methods = tk.Frame(parent, bg=APP_BG)
        methods.pack(fill="x", padx=12, pady=6)
        tk.Radiobutton(
            methods, text="Clear — 1 pass of 0x00", variable=self.erase_method, value="clear",
            bg=APP_BG, fg=INK, selectcolor=CARD_BG, activebackground=APP_BG, activeforeground=INK,
        ).pack(side="left", padx=(0, 16))
        tk.Radiobutton(
            methods, text="Purge — 3 passes (0x00, 0xFF, random)", variable=self.erase_method, value="purge",
            bg=APP_BG, fg=INK, selectcolor=CARD_BG, activebackground=APP_BG, activeforeground=INK,
        ).pack(side="left")

        tk.Button(
            parent, text="Run secure-erasure demo", command=self._run_erasure, bg=ACCENT, fg="#081018"
        ).pack(anchor="w", padx=12, pady=8)

        self.erase_log.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.erase_log.insert(
            "1.0",
            "Waiting.\n\nTypical demo story:\n"
            "1. Hash the working copy (before).\n"
            "2. Overwrite every byte.\n"
            "3. Hash again (after) — the digest changes.\n"
            "4. Original evidence file is left untouched.\n",
        )

    # ------------------------------------------------------------------ actions
    def _pick_image(self) -> None:
        path = filedialog.askopenfilename(
            title="Select forensic image",
            filetypes=[
                ("Raw images", "*.img *.dd *.raw *.bin"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.image_path.set(path)

    def _pick_out(self) -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.out_dir.set(path)

    def _pick_erase_file(self) -> None:
        path = filedialog.askopenfilename(title="Select a regular file to copy and overwrite")
        if path:
            self.erase_src.set(path)

    def _require_paths(self) -> tuple[Path, Path] | None:
        if not self.image_path.get() or not self.out_dir.get():
            messagebox.showwarning("Missing paths", "Please choose both an image file and an output folder.")
            return None
        image = Path(self.image_path.get())
        if not image.is_file():
            messagebox.showerror("Not found", f"Image does not exist:\n{image}")
            return None
        return image, Path(self.out_dir.get())

    def _hash_only(self) -> None:
        paths = self._require_paths()
        if not paths:
            return
        image, _ = paths
        self.status.set("Hashing source image (read-only)...")
        self.update_idletasks()
        digest = sha256_file(image)
        self.hash_text.set(f"SHA-256: {digest}")
        self.status.set("Hash complete. Evidence was not modified.")

    def _start_recovery(self) -> None:
        if self._busy:
            return
        paths = self._require_paths()
        if not paths:
            return
        image, out_dir = paths
        self._busy = True
        self.status.set("Starting recovery...")
        thread = threading.Thread(target=self._recovery_worker, args=(image, out_dir), daemon=True)
        thread.start()

    def _recovery_worker(self, image: Path, out_dir: Path) -> None:
        try:
            def progress(msg: str, _frac: float) -> None:
                self.after(0, lambda m=msg: self.status.set(m))

            self.after(0, lambda: self.status.set("Computing SHA-256 of source image..."))
            digest = sha256_file(image)
            self.after(0, lambda: self.hash_text.set(f"SHA-256: {digest}"))

            recovered = carve_image(image, out_dir, progress_cb=progress)
            json_path = out_dir / "case_report.json"
            html_path = out_dir / "case_report.html"
            write_reports(
                source_image=image,
                source_hash_sha256=digest,
                files=recovered,
                json_path=json_path,
                html_path=html_path,
                image_size=image.stat().st_size,
            )
            self.report_path = json_path
            self.html_path = html_path
            self.after(0, lambda: self._show_results(recovered, json_path, html_path))
        except Exception as exc:  # noqa: BLE001 — surface any failure in the UI
            self.after(0, lambda: messagebox.showerror("Recovery failed", str(exc)))
            self.after(0, lambda: self.status.set(f"Error: {exc}"))
        finally:
            self._busy = False

    def _show_results(self, recovered, json_path: Path, html_path: Path) -> None:
        for row in self.tree.get_children():
            self.tree.delete(row)
        for item in recovered:
            self.tree.insert(
                "",
                "end",
                values=(
                    item.filename,
                    item.type,
                    item.offset_start,
                    item.size,
                    item.confidence,
                ),
            )
        by_type = count_by_type(recovered)
        breakdown = "  ".join(f"{k}: {v}" for k, v in sorted(by_type.items())) or "none"
        self.summary_text.set(f"Recovered: {len(recovered)} file(s)   {breakdown}")
        self.status.set(f"Done. JSON: {json_path}   HTML: {html_path}")

    def _open_html(self) -> None:
        if not self.html_path or not self.html_path.is_file():
            messagebox.showinfo("No report yet", "Run recovery first — an HTML report will be written to the output folder.")
            return
        webbrowser.open(self.html_path.resolve().as_uri())

    def _run_erasure(self) -> None:
        src = self.erase_src.get().strip()
        if not src:
            messagebox.showwarning("No file", "Choose a regular file. We will overwrite a COPY of it, not the original.")
            return
        out = self.out_dir.get().strip() or str(Path.cwd() / "recovered")
        try:
            result = demo_erase(src, out, method=self.erase_method.get())
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Erasure demo failed", str(exc))
            return
        self.erase_log.delete("1.0", "end")
        self.erase_log.insert(
            "1.0",
            "\n".join(
                [
                    "Secure erasure demo finished.",
                    f"Method:           {result.method} ({result.passes} pass(es))",
                    f"Original file:    {result.source_file}  (UNCHANGED)",
                    f"Working copy:     {result.working_copy}  (OVERWRITTEN)",
                    f"Bytes:            {result.bytes_overwritten}",
                    f"SHA-256 before:   {result.hash_before}",
                    f"SHA-256 after:    {result.hash_after}",
                    f"Hash changed:     {result.verified}",
                    "",
                    result.message,
                ]
            ),
        )


def main() -> None:
    app = ForensicRecoverApp()
    app.mainloop()


if __name__ == "__main__":
    main()
