"""
Publikuje katalog public/ bezpośrednio na odseparowaną gałąź gh-pages.
Zawiera procedurę pre-flight sanity checks blokującą publikację uszkodzonych buildów.
"""
import os
import subprocess
import sys
from pathlib import Path

def run_cmd(cmd, env=None, check=True):
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if check and res.returncode != 0:
        err = res.stderr.strip() or res.stdout.strip()
        raise RuntimeError(f"Blad komendy {' '.join(cmd)}: {err}")
    return res.stdout.strip()

def validate_build_artifacts(public_dir: Path):
    """
    Sprawdza spójność i poprawność wygenerowanego katalogu public/ przed wdrożeniem.
    Rzuca wyjątek w przypadku wykrycia pustych stron, zerwanych tagów lub braków krytycznych.
    """
    print("[SANITY CHECK] Rozpoczynanie walidacji integralnosci katalogu public/...")
    
    if not public_dir.exists() or not public_dir.is_dir():
        raise ValueError(f"Katalog docelowy {public_dir} nie istnieje!")

    index_file = public_dir / "index.html"
    if not index_file.exists():
        raise ValueError("Krytyczny brak: plik public/index.html nie istnieje!")

    # 1. Weryfikacja rozmiaru index.html (musi mieć co najmniej 3 KB)
    index_size = index_file.stat().st_size
    if index_size < 3072:
        raise ValueError(f"public/index.html jest podejrzanie maly ({index_size} bajtow)! Minimalny prog: 3072 bajty.")

    # 2. Weryfikacja struktury HTML w index.html
    content = index_file.read_text(encoding="utf-8", errors="ignore")
    if "<!DOCTYPE html>" not in content and "<html" not in content:
        raise ValueError("public/index.html nie zawiera prawidlowej deklaracji HTML!")
    if "</html>" not in content:
        raise ValueError("public/index.html jest uciety (brak zamykajacego znacznika </html>)!")

    # 3. Wyszukanie wszystkich plików HTML i wykrywanie plików 0-bajtowych
    html_files = list(public_dir.rglob("*.html"))
    total_html = len(html_files)
    if total_html < 5:
        raise ValueError(f"Wykryto tylko {total_html} plikow HTML. Build jest prawdopodobnie niekompletny!")

    zero_byte_files = [str(f.relative_to(public_dir)) for f in html_files if f.stat().st_size == 0]
    if zero_byte_files:
        sample = zero_byte_files[:5]
        raise ValueError(f"Wykryto {len(zero_byte_files)} pustych (0-bajtowych) plikow HTML! Przyklady: {sample}")

    size_kb = round(index_size / 1024, 2)
    print(f"[SANITY CHECK OK] Zweryfikowano {total_html} plikow HTML. Glowny index.html ma {size_kb} KB. Brak pustych plikow.")

def main():
    root = Path(__file__).resolve().parent.parent
    public_dir = root / "public"

    try:
        validate_build_artifacts(public_dir)
    except Exception as e:
        print(f"[BLOKADA DEPLOYMENTU] Pre-flight sanity check nie powiodl sie: {e}")
        print("Deployment przerwany. Popraw bledy w generatorze lub bazie przed publikacja.")
        sys.exit(1)

    nojekyll = public_dir / ".nojekyll"
    if not nojekyll.exists():
        nojekyll.write_text("", encoding="utf-8")
        print("[OK] Utworzono public/.nojekyll")

    temp_index = root / ".git" / "temp_gh_pages_idx"
    if temp_index.exists():
        temp_index.unlink()

    custom_env = os.environ.copy()
    custom_env["GIT_INDEX_FILE"] = str(temp_index)

    try:
        print("[1/4] Przygotowywanie drzewa plikow public/...")
        run_cmd(["git", "--work-tree=public", "add", "-A"], env=custom_env)

        print("[2/4] Zapisywanie drzewa obiektow (write-tree)...")
        tree_sha = run_cmd(["git", "write-tree"], env=custom_env)

        print(f"[3/4] Generowanie commita dla drzewa {tree_sha[:8]}...")
        parent_sha = None
        remotes = run_cmd(["git", "ls-remote", "--heads", "origin", "gh-pages"], check=False)
        if remotes and "refs/heads/gh-pages" in remotes:
            parent_sha = remotes.split()[0]

        commit_cmd = ["git", "commit-tree", tree_sha, "-m", "chore(deploy): publish static site to gh-pages [validated]"]
        if parent_sha:
            commit_cmd.extend(["-p", parent_sha])

        commit_sha = run_cmd(commit_cmd, env=custom_env)

        print(f"[4/4] Wypychanie commita {commit_sha[:8]} do origin/gh-pages...")
        push_res = run_cmd(["git", "push", "origin", f"{commit_sha}:refs/heads/gh-pages", "--force"])
        print("[SUKCES] Deployment zakonczony pomyslnie po pozytywnym tescie integralnosci.")
        print(push_res)
    finally:
        if temp_index.exists():
            temp_index.unlink()

if __name__ == "__main__":
    main()