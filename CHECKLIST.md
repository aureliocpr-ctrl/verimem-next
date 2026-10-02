# Checklist di sviluppo

Questa è la mappa del lavoro. Chi riprende parte da qui e da [`HANDOFF.md`](HANDOFF.md).

Regole d'uso:
- Ogni voce ha un criterio di "fatto". Una voce si spunta solo quando il criterio è
  verificato con un comando, e il comando è scritto accanto.
- Una sessione prende una voce (o poche voci piccole), non una fase intera.
- Alla fine della sessione: spunta, aggiorna `HANDOFF.md`, fai commit.

Legenda: `[x]` fatto · `[ ]` da fare · `[~]` in corso · `[!]` bloccato (motivo accanto)

---

## Fase 0 — Fondamenta

- [x] **Repository e pacchetto.** Licenza Apache-2.0, `pyproject.toml` (setuptools, layout
  `src/`, extra `nli`, `mcp`, `dev`), `.gitignore`.
  Fatto quando: `pip install -e ".[dev]"` va a buon fine e `python -c "import verimem"` funziona.
- [x] **Documenti di base.** `docs/DESIGN.md`, ADR 0001-0009, questa checklist,
  `HANDOFF.md`, `CLAUDE.md`, `docs/BUSINESS.md`.
  Fatto quando: i file esistono e si rimandano a vicenda.
- [~] **CI.** (workflow scritto, da verificare al primo push) GitHub Actions: `ruff check` e `pytest -m "not model"` su Linux e Windows,
  Python 3.10 e 3.12, senza scaricare modelli.
  Fatto quando: il primo push su GitHub ha la CI verde.
- [!] **Repository su GitHub.** Bloccato: l'integrazione di questa sessione non può creare
  repository. Aurelio crea `aureliocpr-ctrl/verimem-next` vuoto e dà accesso all'app Claude.
  Fatto quando: `git push -u origin main` riesce.

## Fase 1 — Il verificatore

- [x] **Testo** (`text.py`): frasi con offset (italiano e inglese, abbreviazioni, decimali,
  righe di chat, elenchi), normalizzazione, lingua (it/en/und), token di contenuto.
  Fatto quando: `pytest tests/test_text.py` passa.
- [x] **Quantità** (`numbers.py`): cifre, numeri in parole IT/EN, migliaia/decimali ambigui
  in entrambi i sensi, percentuali, scale (k, M, mila, milioni), date con mesi IT/EN, ore.
  Fatto quando: `pytest tests/test_numbers.py` passa, inclusi i casi della revisione
  ("1,520" contro "1,250", "1000" contro "100", un "40%" mai detto, "tre" contro "3").
- [x] **Giudici** (`judges/`): protocollo `Judge`; `HFNLIJudge` con mappatura delle
  etichette per nome esatto e controllo d'orientamento al caricamento; `LexicalJudge`
  come linea di base, mai abilitato a verificare.
  Fatto quando: test con giudice finto passano; il test `model` con bge-m3 passa.
- [x] **Policy** (`policy.py`, `policies/default.json`): soglie per lingua, versione,
  provenienza della calibrazione.
  Fatto quando: `pytest tests/test_policy.py` passa.
- [x] **Verificatore** (`verifier.py`): finestre, prefiltro, veto sulle quantità, decisione,
  evidenza con offset, `check_many` in un'unica chiamata al giudice.
  Fatto quando: test con giudice finto passano, e con bge-m3 vero i 34 casi veri/aggiunte
  della revisione danno AUROC 1,00 (lo stesso numero del bake-off).

## Fase 2 — La memoria

- [x] **Store** (`store.py`): schema v1, migrazioni, FTS5, transazioni, id ordinabili nel tempo.
- [x] **Audit** (`audit.py`): catena di hash, verifica, esportazione JSONL; solo hash, mai testo.
  Fatto quando: un test di manomissione trova la riga alterata.
- [x] **Memory** (`memory.py`): `remember` (fiducia nella fonte, verifica, stato,
  supersessione per `subject`), `get`, `history`, `review`, `forget`, `stats`.
- [x] **Invarianti come test**: `verified` solo con giudice-modello o revisione umana; la
  mappatura verdetto→stato sta in una sola funzione; `forget` non lascia testo nel database;
  la catena resta valida dopo `forget`.
  Fatto quando: `pytest tests/test_memory.py tests/test_invariants.py` passa.

## Fase 3 — Lettura e astensione

- [ ] **recall**: BM25 su FTS5, filtro per stato (default solo `verified`), evidenza e
  provenienza in ogni risultato.
- [ ] **Pertinenza** (`relevance.py`): con lo stesso modello NLI e un modello di ipotesi
  IT/EN; interfaccia aperta ad altri modelli.
- [ ] **ask**: risponde con i fatti pertinenti o si astiene, con il motivo.
- [ ] **Misura dell'astensione** su `datasets/qa-mini.jsonl` (domande con e senza risposta).
  Fatto quando: `verimem eval-ask datasets/qa-mini.jsonl` stampa astensioni giuste/sbagliate
  e la soglia in policy viene da lì.

## Fase 4 — Valutazione e calibrazione

- [ ] **evalkit**: CSV/JSONL (anche colonne italiane fonte/fatto/etichetta), AUROC con
  intervallo bootstrap, soglie su metà e misura sull'altra metà, per lingua, latenza,
  linea di base lessicale.
- [ ] **calibrate**: scrive una policy JSON con la provenienza.
- [ ] **Dataset di regressione** `datasets/mini-it-en.csv`: scritto da Claude, etichettato,
  dichiarato come tale. Serve a non regredire, non a dimostrare niente.
- [ ] **docs/EVAL.md** generato da `verimem eval ... --markdown docs/EVAL.md`.

## Fase 5 — Il rapporto di affidabilità della memoria (il prodotto che si vende per primo)

- [ ] **report.py**: `audit_pairs(coppie)` → JSON completo + Markdown leggibile (quante
  memorie la fonte sostiene, quante no, esempi con l'evidenza, numeri inventati, giudice e
  policy usati, limiti dichiarati).
- [ ] **CLI** `verimem audit coppie.jsonl --out cartella/`.
- [ ] **Esempio completo** in `examples/` con il rapporto generato e versionato.

## Fase 6 — Interfacce

- [ ] **CLI** completa: check, remember, recall, ask, review, forget, stats, audit, eval,
  calibrate, chain, warmup, doctor, mcp.
- [ ] **Server MCP** (FastMCP): remember, recall, ask, check, review_queue, review, forget,
  stats; giudice caricato all'avvio; test in-process.
- [ ] **Quickstart del README** eseguito davvero, output incollato dall'esecuzione.

## Fase 7 — Rilascio

- [ ] Wheel costruita e installata in un venv pulito; smoke test.
- [ ] README onesto: cosa fa, cosa non fa, numeri presi da `docs/EVAL.md`.
- [ ] CHANGELOG e versione 0.9.0.
- [ ] Pubblicazione su PyPI: **solo con l'ok di Aurelio** (il nome `verimem` è già suo).

## Fase 8 — Cancello 1 (lavoro di Aurelio, non di codice)

- [ ] Esportare 300 coppie dal proprio store, etichettarle S/N/C, lanciare `verimem eval`.
  Decide la regola scritta in `docs/BUSINESS.md`, non il giorno dopo.

## Fase 9 — Mercato

- [ ] Pagina dell'offerta "Memory Reliability Audit" (IT/EN).
- [ ] Bozza di post (IT/EN) con i numeri veri; lista di 30 contatti; messaggio di contatto.
- [ ] Pubblicazione nel registro MCP (dopo la fase 7).

## Fase 10 — Solo dopo il primo segnale pagante

- [ ] Adapter Mem0 e LangGraph store.
- [ ] API HTTP (FastAPI) e immagine Docker.
- [ ] Giudice LLM opzionale per i casi incerti (solo opt-in, ADR-0008).
- [ ] Embedding opzionali per il recupero ibrido.
- [ ] Console di revisione dei fatti in quarantena.
- [ ] Conflitti automatici fra fatti con un giudice a tre vie.
- [ ] Euristica contro le istruzioni nascoste nelle memorie (prompt injection), con eval.
