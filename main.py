"""
===============================================================================
ΣΚΑΝΕΡ ΑΡΧΕΙΩΝ PDF by drosopoulos @github
===============================================================================

1. ΑΠΑΡΑΙΤΗΤΑ ΕΡΓΑΛΕΙΑ
   ----------------------------------
   Κατέβασε τη βιβλιοθήκη pypdf  
       pip install pypdf

2. ΔΟΜΗ ΦΑΚΛΩΝ
   ---------------
   Βάλε όλα τα pdf σε έναν φάκελο και ονόμασέ τον "db". Αυτόν τον φάκελο να τον έχεις μέσα στον ίδιο φάκελο με το πρόγραμμα.  

       project_folder/
       ├── main.py
       └── db/
           ├── document1.pdf
           └── document2.pdf...

3. ΑΠΑΡΑΙΤΗΤΟ ΠΡΟΓΡΑΜΜΑ ΓΙΑ ΤΟ OCR VERSION
   ---------------------------------------
   Κατέβασε με τις εντολές:

   * Linux Fedora:
       sudo dnf update
       sudo dnf install poppler-utils tesseract-ocr tesseract-ocr-ell

   * Windows:
       Κατέβασε και εγκατέστησε το Poppler κανονικά και βάλτο στο PATH

4. USAGE EXAMPLES
   --------------
   - Βασική λειτουργία (δεν είναι case-sensitive, γράφεις σε αγγλικά ή/και ελληνικα):
       python main.py
        ή απευθείας τρέξε:
       python3 main.py --keywords "φασκομηλο, 12, κανναβη"

    - Άμα θες να είναι case-sensitive τρέξε¨
       python3 main.py --keywords "ΦΑΣΚΟΜΗΛΟ" --case-sensitive

       ####ΓΙΑ ΕΛΛΗΝΙΚΑ ΠΟΥ ΔΕΝ ΕΙΝΑΙ ΚΑΛΟΓΡΑΜΜΕΝΑ Ή ΕΙΝΑΙ ΣΚΑΝΑΡΙΣΜΕΝΑ ΚΑΙ ΔΕΝ ΜΕΤΑΓΡΑΦΟΝΤΑΙ ΣΩΣΤΑ ΟΙ ΧΑΡΑΚΤΗΡΕΣ:
   - Τυπικό για ελληνικά:
       python3 main.py --ocr

   - Αν μπαγκάρει η αναζήτηση με πολλές γλώσσες βάλε:
       python3 main.py --ocr --ocr-lang eng
       python3 main.py --ocr --ocr-lang "ell+eng"
===============================================================================
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("The 'pypdf' package is required. Install it with:\n    pip install pypdf")
    sys.exit(1)


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped).casefold()


def get_script_dir() -> Path:
    return Path(__file__).resolve().parent


def get_keywords_from_user() -> list[str]:
    raw = input("Βάλε λέξεις-κλειδιά (διαχωρισμένες με κόμμα): ").strip()
    keywords = [kw.strip() for kw in raw.split(",") if kw.strip()]
    if not keywords:
        print("Δεν εισήχθησαν λέξεις-κλειδιά. Έξοδος.")
        sys.exit(1)
    return keywords


def extract_text_from_pdf(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        text_parts = []
        for page in reader.pages:
            try:
                text_parts.append(page.extract_text() or "")
            except Exception as page_err:
                print(f"  [warning] Could not read a page in {pdf_path.name}: {page_err}")
        return "\n".join(text_parts)
    except Exception as e:
        print(f"  [error] Could not open {pdf_path.name}: {e}")
        return ""


def check_ocr_tools_available(ocr_lang: str):
    missing = []
    if shutil.which("pdftoppm") is None:
        missing.append("pdftoppm (install poppler-utils)")
    if shutil.which("tesseract") is None:
        missing.append("tesseract (install tesseract-ocr)")
    if missing:
        print("OCR mode requires these system tools, which were not found:")
        for m in missing:
            print(f"  - {m}")
        sys.exit(1)

    try:
        result = subprocess.run(
            ["tesseract", "--list-langs"], capture_output=True, text=True, check=True
        )
        available_langs = result.stdout.splitlines()[1:]
        if ocr_lang not in available_langs:
            print(f"Tesseract language pack '{ocr_lang}' not found.")
            print(f"Available languages: {', '.join(available_langs)}")
            print(f"Install it (e.g. 'sudo apt-get install tesseract-ocr-{ocr_lang}') and try again.")
            sys.exit(1)
    except Exception as e:
        print(f"[warning] Could not verify tesseract language packs: {e}")


def extract_text_from_pdf_ocr(pdf_path: Path, ocr_lang: str, dpi: int = 200) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        prefix = str(Path(tmpdir) / "page")
        try:
            subprocess.run(
                ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), prefix],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"  [error] pdftoppm failed on {pdf_path.name}: {e.stderr.decode(errors='ignore')}")
            return ""

        page_images = sorted(Path(tmpdir).glob("page-*.png"))
        if not page_images:
            print(f"  [error] No pages rendered for {pdf_path.name}")
            return ""

        text_parts = []
        for img_path in page_images:
            try:
                result = subprocess.run(
                    ["tesseract", str(img_path), "stdout", "-l", ocr_lang],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                text_parts.append(result.stdout)
            except subprocess.CalledProcessError as e:
                print(f"  [warning] OCR failed on a page of {pdf_path.name}: {e.stderr}")

        return "\n".join(text_parts)


def search_pdfs(db_folder: Path, keywords: list[str], case_sensitive: bool = False,
                 use_ocr: bool = False, ocr_lang: str = "ell"):
    if not db_folder.exists():
        print(f"Folder not found: {db_folder}")
        sys.exit(1)

    pdf_files = sorted(db_folder.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {db_folder}")
        sys.exit(0)

    if use_ocr:
        check_ocr_tools_available(ocr_lang)

    flagged = {}

    mode_label = f"OCR (lang={ocr_lang})" if use_ocr else "text extraction"
    print(f"\nScanning {len(pdf_files)} PDF file(s) in '{db_folder.name}' using {mode_label}...\n")

    for pdf_path in pdf_files:
        print(f"Reading: {pdf_path.name}")

        if use_ocr:
            text = extract_text_from_pdf_ocr(pdf_path, ocr_lang)
        else:
            text = extract_text_from_pdf(pdf_path)

        if not text.strip():
            print("  [note] No extractable text found.")
            continue

        search_text = text if case_sensitive else normalize_text(text)

        matches = {}
        for kw in keywords:
            needle = kw if case_sensitive else normalize_text(kw)
            count = search_text.count(needle)
            if count > 0:
                matches[kw] = count

        if matches:
            flagged[pdf_path.name] = matches
            match_summary = ", ".join(f"'{k}' x{v}" for k, v in matches.items())
            print(f"  -> FLAGGED: {match_summary}")
        else:
            print("  -> No keywords found.")

    return flagged


def print_summary(flagged: dict, keywords: list[str]):
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Keywords searched: {', '.join(keywords)}")

    if not flagged:
        print("\nNo documents were flagged. No keywords found in any PDF.")
        return

    print(f"\n{len(flagged)} document(s) flagged:\n")
    for filename, matches in flagged.items():
        match_summary = ", ".join(f"'{k}' ({v} occurrence{'s' if v != 1 else ''})" for k, v in matches.items())
        print(f"  - {filename}: {match_summary}")


def main():
    parser = argparse.ArgumentParser(description="Search PDFs in the 'db' folder for keywords.")
    parser.add_argument(
        "--keywords",
        type=str,
        help="Comma-separated list of keywords (skips the interactive prompt).",
    )
    parser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Make the search case-sensitive (default: case-insensitive).",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Use OCR instead of normal text extraction.",
    )
    parser.add_argument(
        "--ocr-lang",
        type=str,
        default="ell",
        help="Tesseract language code for OCR mode (default: 'ell').",
    )
    args = parser.parse_args()

    script_dir = get_script_dir()
    db_folder = script_dir / "db"

    if args.keywords:
        keywords = [kw.strip() for kw in args.keywords.split(",") if kw.strip()]
        if not keywords:
            print("No valid keywords provided via --keywords.")
            sys.exit(1)
    else:
        keywords = get_keywords_from_user()

    flagged = search_pdfs(
        db_folder, keywords,
        case_sensitive=args.case_sensitive,
        use_ocr=args.ocr,
        ocr_lang=args.ocr_lang,
    )
    print_summary(flagged, keywords)


if __name__ == "__main__":
    main()
