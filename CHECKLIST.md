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
  `HANDOFF.md`, `CLAUDE.md`, `docs/business/BUSINESS.md`.
- [~] **CI.** Workflow scritto (`.github/workflows/ci.yml`: `ruff check` e
  `pytest -m "not model"` su Linux e Windows, Python 3.10 e 3.12, senza modelli).
  Fatto quando: il primo push su GitHub ha la CI verde.
- [!] **Repository su GitHub.** Bloccato: l'integrazione della sessione cloud non può creare
  repository (errore 403). Aurelio crea `aureliocpr-ctrl/verimem-next` vuoto e dà accesso
  all'app Claude. Prima del primo push va deciso se `docs/business/` (piano, prezzi, bozze commerciali)
  può essere pubblico (vedi HANDOFF, decisioni aperte).
  Fatto quando: `git push -u origin main` riesce.

## Fase 1 — Il verificatore

- [x] **Testo** (`text.py`): frasi con offset, normalizzazione, lingua, token di contenuto,
  riconoscimento delle domande. `pytest tests/test_text.py`.
- [x] **Quantità** (`numbers.py`): cifre, numeri in parole IT/EN, separatori ambigui, scale,
  date, ore. `pytest tests/test_numbers.py`.
- [x] **Giudici** (`judges/`): `HFNLIJudge` (etichette per nome, controllo d'orientamento),
  `LexicalJudge` mai abilitato a verificare. `VERIMEM_TEST_MODELS=1 pytest -m model`.
- [x] **Policy** (`policy.py`, `policies/default.json`). `pytest tests/test_policy.py`.
- [x] **Verificatore** (`verifier.py`): finestre (mai solo domande), prefiltro, veto sulle
  quantità, controllo del contesto, evidenza con offset, `check_many` in una chiamata.
  Con bge-m3: AUROC 1,000 sui 40 casi della revisione (`docs/eval/review-cases.md`).

## Fase 2 — La memoria

- [x] **Store** (`store.py`): SQLite + FTS5 (Porter per l'inglese), transazioni,
  cancellazione fisica.
- [x] **Audit** (`audit.py`): catena di hash, solo impronte HMAC, verifica ed esportazione.
- [x] **Memory** (`memory.py`): un solo percorso di scrittura, `status_for` unica mappatura,
  supersessione per `subject`, revisione umana, `forget`.
- [x] **Invarianti come test**, falsificati con mutazioni: `pytest tests/test_invariants.py`.

## Fase 3 — Lettura e astensione

- [x] **recall**: FTS5, solo `verified` per default, evidenza e provenienza.
- [x] **Pertinenza** (`relevance.py`): lo stesso modello NLI con un modello di ipotesi IT/EN.
- [x] **ask**: risponde con i fatti pertinenti o si astiene, con il motivo.
- [x] **Misura dell'astensione**: `verimem eval-ask datasets/qa-mini.json` (17/25 risposte
  giuste, 0 false) e `datasets/qa-heldout.json` (15/25, 2 false). Soglia 0,4 da
  `scripts/research/ask_threshold.py`.
- [ ] **Pertinenza migliore.** `ask` si astiene su 8-10 domande su 25 a cui la memoria sa
  rispondere (es. "Who leads the data platform team?" contro "Anna leads the data platform
  team.", 0,11). Una regola lessicale è stata provata e ritirata (commit cecfccb/09426c3,
  `docs/EVAL.md`). Strade: un modello di riordino con licenza pulita, un giudice LLM
  opzionale (ADR-0008). Prima di ogni prova: un terzo insieme di domande scritto prima.
  Fatto quando: su un insieme mai visto, più risposte giuste senza più risposte false.

## Fase 4 — Valutazione e calibrazione

- [x] **evalkit**: CSV/JSONL (anche intestazioni italiane), AUROC con intervallo bootstrap,
  soglia scelta su metà e misurata sull'altra metà, falsi positivi elencati per primi.
- [x] **calibrate**: scrive una policy JSON con la provenienza. `pytest tests/test_evalkit.py`.
- [x] **Dataset di regressione**: `datasets/review-cases.csv` (40 coppie, scritte da Claude,
  dichiarate come tali), più TruthfulQA (582 coppie, scritte da persone).
- [x] **docs/EVAL.md**: ogni numero con il comando; `scripts/evals.sh` rigenera tutto.

## Fase 5 — Il rapporto di affidabilità della memoria (il prodotto che si vende per primo)

- [x] **report.py**: JSON, Markdown (en/it) e `review.csv`. `pytest tests/test_report.py`.
- [x] **CLI** `verimem audit coppie.jsonl --out cartella/ --lang it`.
- [x] **Ciclo di revisione**: `review.csv` in ordine casuale per gruppo, colonna
  `stated_by_source`; `verimem audit-review cartella/` dà la stima controllata da una
  persona con intervallo al 95%. `pytest tests/test_audit_review.py`.
- [x] **Esempio completo** in `examples/audit/` (dati inventati, dichiarati come tali).

## Fase 6 — Interfacce

- [x] **CLI** completa: check, remember, recall, ask, queue, review, forget, stats, chain,
  audit, audit-review, eval, eval-ask, calibrate, warmup, doctor, mcp. `pytest tests/test_cli.py`.
- [x] **Server MCP** (FastMCP): `review` solo con `--allow-review`; un processo vero su stdio
  in `pytest tests/test_mcp_stdio.py` (avvio, elenco degli strumenti, `remember`).
- [x] **Quickstart del README** eseguito davvero: `python examples/quickstart.py`.

## Fase 7 — Rilascio

- [x] Wheel e sdist costruite (`python -m build`) e installate in ambienti puliti: solo la
  wheel (CLI, `doctor`, giudice lessicale, `audit`, errore chiaro senza l'extra `nli`); la
  wheel con l'extra `mcp` (mcp 2.2: server su stdio con un client vero); la sdist con
  `[dev,mcp]` (138 test passati). Non provato in ambiente pulito: l'extra `nli` (torch),
  provato solo nell'ambiente di sviluppo.
- [x] README onesto: cosa fa, cosa non fa, numeri presi da `docs/EVAL.md`.
- [x] CHANGELOG (`CHANGELOG.md`, 0.9.0 non ancora rilasciata).
- [ ] Versione 0.9.0 al posto di 0.9.0.dev0: insieme alla decisione su PyPI.
- [ ] Pubblicazione su PyPI: **solo con l'ok di Aurelio** (il nome `verimem` è già suo e oggi
  installa la 0.7.x).

## Fase 8 — Cancello 1 (lavoro di Aurelio, non di codice)

- [ ] Esportare 300 coppie dal proprio store, etichettarle S/N/C senza vedere punteggi,
  lanciare `verimem eval`. Istruzioni e regola di decisione (scritta prima):
  [`scripts/gate1/LEGGIMI.md`](scripts/gate1/LEGGIMI.md). L'esportatore è provato su uno store
  sintetico con lo schema della 0.7, non sullo store vero.
  Fatto quando: la regola dice passa o non passa, e la policy calibrata (se passa) è in commit.

## Fase 9 — Mercato

- [x] Pagina dell'offerta "Memory Reliability Audit" (IT/EN): bozze in `docs/business/`,
  manca il prezzo (decisione di Aurelio).
- [x] Manuale di consegna dell'audit (`docs/business/consegna-audit.md`), con il numero di
  memorie da rivedere da `scripts/research/review_sample_size.py`.
- [x] Bozza di post (IT/EN) con i numeri veri e i limiti; messaggi di contatto e criteri per
  trovare i clienti (`docs/business/`). Le cifre di mercato citate sono state ricontrollate
  con le fonti il 2026-10-02.
- [ ] Lista di 30 contatti (lavoro di Aurelio: relazioni e scelta dei nomi).
- [ ] Pubblicazione nel registro MCP (dopo il primo push e la scelta su PyPI).

## Fase 10 — Solo dopo il primo segnale pagante

- [ ] Esportatori per Mem0, Zep, LangGraph store (coppie fonte-memoria per `verimem audit`).
- [ ] API HTTP (FastAPI) e immagine Docker.
- [ ] Giudice LLM opzionale per i casi incerti (solo opt-in, ADR-0008).
- [ ] Embedding opzionali per il recupero ibrido (anche fra lingue diverse).
- [ ] Console di revisione dei fatti in quarantena.
- [ ] Conflitti automatici fra fatti con un giudice a tre vie.
- [ ] Euristica contro le istruzioni nascoste nelle memorie (prompt injection), con eval.

## Piccole cose note, da fare quando si tocca il codice vicino

- [ ] Il verdetto registra giudice e policy ma non la versione di verimem che l'ha prodotto:
  aggiungerla prima del rilascio, se no i verdetti di versioni diverse non si distinguono.
- [ ] Le domande nella fonte possono ancora prestare il loro presupposto a un'affermazione
  (TruthfulQA: "Why does the government lie about…?"). Casi in `docs/EVAL.md`.
- [ ] `verimem eval` calcola l'AUROC per lingua ma il Markdown non lo mostra.
- [ ] Le quantità negate ("not signed on July 4") fanno scattare il veto.
