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

## Prossimo passo

Fase 2: `store.py` (schema SQLite + FTS5), `audit.py` (catena di hash), `memory.py`
(remember con fiducia nella fonte e supersessione, review, forget) e i test degli invarianti.

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
