# Passaggio di consegne

Ultimo aggiornamento: 2026-10-02, sessione cloud di Claude (riscrittura da zero).

## Dove siamo

- **Fase 0 (fondamenta)**: pacchetto, licenza, documenti, CI scritti. Manca il repository
  su GitHub: l'integrazione della sessione non può crearlo (errore 403). Il lavoro è in
  commit locali, pronti da pubblicare.
- **Fase 1 (verificatore)**: completa. `text.py`, `numbers.py`, `judges/`, `policy.py`,
  `verifier.py` con test. Con il giudice vero (bge-m3-zeroshot-v2.0-c, revisione
  705510dfe0f3) i 40 casi della revisione sono separati: 15/15 veri `supported`,
  0/25 aggiunte o contraddizioni `supported` (`VERIMEM_TEST_MODELS=1 pytest -m model`).

## Come si lavora

```
pip install -e ".[dev,nli,mcp]"
ruff check src tests
pytest -m "not model"
VERIMEM_TEST_MODELS=1 pytest -m model
```

- **Fase 2 (memoria)**: completa. `store.py` (SQLite + FTS5, cancellazione fisica),
  `audit.py` (catena di hash con impronte HMAC, mai testo), `memory.py` (un solo percorso di
  scrittura, `status_for` unica funzione di mappatura, supersessione per `subject`,
  revisione umana, `forget`). Gli invarianti di DESIGN §3 sono test, falsificati con mutazioni
  (`tests/test_invariants.py`). Nota: questa build di SQLite ha `secure_delete` già attivo;
  il codice lo forza comunque, perché altre build no.

## Prossimo passo

Fase 3: misurare `ask` (astensione). Serve un piccolo set di domande con e senza risposta
(`datasets/qa-mini.jsonl`) e un comando che stampi astensioni giuste e sbagliate per
scegliere il modello di ipotesi e la soglia di pertinenza con i numeri.

## Decisioni aperte per Aurelio

1. Creare il repository `aureliocpr-ctrl/verimem-next` (vuoto, pubblico) e dare accesso
   all'app Claude, così il lavoro si pubblica.
2. Quando sarà pronto: pubblicare su PyPI con il nome `verimem` (sostituisce la 0.7.6)?
3. Più avanti: rinominare questo repo in `verimem` e archiviare il vecchio?

## Problemi noti

- Il giudice predefinito è binario: le contraddizioni escono come `not_supported`, non
  `contradicted` (ADR-0007).
- Le soglie della policy predefinita sono provvisorie finché non c'è il Cancello 1 su dati
  veri (fase 8).
