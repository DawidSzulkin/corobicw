"""
Publikuje katalog public/ bezpośrednio na odseparowaną gałąź gh-pages.
Działa w 100% lokalnie, używając natywnego git plumbing (bez przełączania brancha roboczego).
"""
import os
import subprocess
import sys
from pathlib import Path

def run_cmd(cmd, env=None, check=True):
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        raise RuntimeError(f"Błąd komendy {' '.join(cmd)}: {err}")
    return res.stdout.strip()

def main():
    root = Path(__file__).resolve().parent.parent
    public_dir = root / "public"

    if not public_dir.exists() or not (public_dir / "index.html").exists():
        print("[BŁĄD] Katalog public/ nie istnieje lub nie zawiera index.html! Wygeneruj najpierw serwis.")
        sys.exit(1)

    # 1. Zapewnienie pliku .nojekyll (ochrona przed parserem Jekyll na GitHub Pages)
    nojekyll = public_dir / ".nojekyll"
    if not nojekyll.exists():
        nojekyll.write_text("", encoding="utf-8")
        print("[OK] Utworzono public/.nojekyll")

    # 2. Tymczasowy indeks Gita (izolacja od głównego drzewa roboczego)
    temp_index = root / ".git" / "temp_gh_pages_idx"
    if temp_index.exists():
        temp_index.unlink()

    custom_env = os.environ.copy()
    custom_env["GIT_INDEX_FILE"] = str(temp_index)

    try:
        print("[1/4] Przygotowywanie drzewa plików public/...")
        run_cmd(["git", "--work-tree=public", "add", "-A"], env=custom_env)

        print("[2/4] Zapisywanie drzewa obiektów (write-tree)...")
        tree_sha = run_cmd(["git", "write-tree"], env=custom_env)

        print(f"[3/4] Generowanie commita dla drzewa {tree_sha[:8]}...")
        # Sprawdzenie czy na originie istnieje już gałąź gh-pages
        parent_sha = None
        remotes = run_cmd(["git", "ls-remote", "--heads", "origin", "gh-pages"], check=False)
        if remotes and "refs/heads/gh-pages" in remotes:
            parent_sha = remotes.split()[0]

        commit_cmd = ["git", "commit-tree", tree_sha, "-m", "chore(deploy): publish static site to gh-pages"]
        if parent_sha:
            commit_cmd.extend(["-p", parent_sha])

        commit_sha = run_cmd(commit_cmd, env=custom_env)

        print(f"[4/4] Wypychanie commita {commit_sha[:8]} do origin/gh-pages...")
        push_res = run_cmd(["git", "push", "origin", f"{commit_sha}:refs/heads/gh-pages", "--force"])
        print("[SUKCES] Deployment zakończony. Artefakty opublikowane na gałęzi gh-pages.")
        print(push_res)
    finally:
        if temp_index.exists():
            temp_index.unlink()

if __name__ == "__main__":
    main()