"""Cancello 1, passo 1: estrae dal tuo store verimem coppie (fonte, fatto) da etichettare.

Prende i fatti che hanno un estratto di fonte salvato (colonna grounding_span, presente
dai fatti scritti con una fonte dall'8 agosto 2026 in poi), ne sceglie un campione a caso
e scrive un CSV da aprire con Excel. NON esporta il punteggio del giudice: le etichette
vanno date senza vederlo.

Lo store viene aperto in SOLA LETTURA.

Uso:
    python esporta_coppie.py                       # store di default, 300 coppie
    python esporta_coppie.py --db PERCORSO\\semantic.db --n 400 --out coppie.csv
"""
from __future__ import annotations

import argparse
import csv
import random
import sqlite3
from pathlib import Path

DEFAULT_DB = Path.home() / ".engram" / "semantic" / "semantic.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=Path("coppie_da_etichettare.csv"))
    a = ap.parse_args()

    if not a.db.exists():
        raise SystemExit(f"Store non trovato: {a.db}")
    con = sqlite3.connect(f"file:{a.db.as_posix()}?mode=ro", uri=True)
    rows = con.execute(
        "SELECT id, proposition, grounding_span FROM facts "
        "WHERE grounding_span IS NOT NULL AND length(trim(grounding_span)) > 0 "
        "AND superseded_by IS NULL"
    ).fetchall()
    con.close()
    print(f"fatti con estratto di fonte: {len(rows)}")
    if not rows:
        raise SystemExit("Nessun fatto con grounding_span: servono coppie da un'altra fonte "
                         "(vedi LEGGIMI_CANCELLO1.txt, punto 2).")
    random.Random(a.seed).shuffle(rows)
    rows = rows[: a.n]

    # punto e virgola + BOM: si apre bene con Excel in italiano
    with a.out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["id", "lingua", "fonte", "fatto", "etichetta", "note"])
        for fid, prop, span in rows:
            w.writerow([fid, "", " ".join(span.split()), " ".join(prop.split()), "", ""])
    print(f"scritte {len(rows)} coppie in {a.out}")
    print("Colonna 'etichetta': S = la fonte lo dice o lo implica senza dubbi, "
          "N = plausibile ma la fonte non lo dice, C = la fonte dice il contrario. "
          "Colonna 'lingua': IT o EN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
