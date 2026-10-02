# Passaggio di consegne

Ultimo aggiornamento: 2026-10-02, sessione cloud di Claude (riscrittura da zero).

## Dove siamo

Fasi 1-6 della [checklist](CHECKLIST.md) fatte: verificatore, memoria, lettura con
astensione, valutazione, rapporto di affidabilità con ciclo di revisione, CLI e server MCP.
Tutto è in commit locali: il repository su GitHub non esiste ancora (vedi sotto).

Cosa funziona, misurato (`docs/EVAL.md`, ogni numero con il suo comando):

- **Verificatore** con bge-m3-zeroshot-v2.0-c: sui 40 casi della revisione 15/15 veri
  verificati e 0/25 aggiunte o contraddizioni; su 582 coppie TruthfulQA (scritte da persone)
  AUROC 0,821, 10 idee sbagliate su 300 verificate (3,3%).
- **Rapporto** (`verimem audit`, `verimem audit-review`): esempio completo in
  `examples/audit/`, in italiano e inglese, su dati inventati.
- **MCP**: provato con un processo vero su stdio (`tests/test_mcp_stdio.py`).

Cosa è debole, misurato:

- **`ask` si astiene troppo**: 8 e 10 domande su 25 a cui la memoria sa rispondere, sui due
  insiemi di domande. Una regola lessicale per migliorarla ha funzionato sull'insieme su cui
  era disegnata e non su quello tenuto da parte: ritirata (commit cecfccb e 09426c3).
- **Nessun numero viene da dati reali.** Le soglie restano provvisorie fino al Cancello 1.

Suite: `pytest -m "not model"` → 138 test passati (con mcp 1.30 e con mcp 2.2); `ruff check src tests` pulito;
`VERIMEM_TEST_MODELS=1 pytest -m model` → 2 passati (ultima esecuzione: 2026-10-02).

## Come si lavora

```
pip install -e ".[dev,nli,mcp]"
verimem warmup
ruff check src tests
pytest -m "not model"
VERIMEM_TEST_MODELS=1 pytest -m model
scripts/evals.sh            # rigenera docs/eval/ e examples/audit/ (4 minuti su 4 CPU)
```

Regole in [`CLAUDE.md`](CLAUDE.md). La più importante imparata qui: una modifica si
disegna su un insieme di dati e si giudica su un altro scritto prima.

## Prossimo passo

1. **Fase 7**: fatta tranne versione e PyPI, che aspettano Aurelio.
2. **Fase 9, mercato**: pagina dell'offerta "Memory Reliability Audit" e messaggio di
   contatto, con i numeri di `docs/EVAL.md` e il rapporto di esempio.
3. Per Aurelio, quando vuole: **Cancello 1** con `scripts/gate1/LEGGIMI.md`.

## Decisioni aperte per Aurelio

1. **Creare il repository** `aureliocpr-ctrl/verimem-next` (vuoto) e dare accesso all'app
   Claude: senza, il lavoro resta in questa sessione. Poi il primo push e la CI.
2. **`docs/BUSINESS.md` in un repository pubblico?** Contiene prezzi ipotizzati, clienti
   tipo e criteri di stop. Se il repository sarà pubblico e non vuoi che si vedano, va tolto
   dalla storia **prima** del primo push (una riscrittura dei commit locali, facile adesso,
   difficile dopo).
3. **PyPI**: pubblicare questa versione con il nome `verimem` (oggi installa la 0.7.x)?
4. Più avanti: rinominare questo repository in `verimem` e archiviare il vecchio?

## Problemi noti

- Il giudice predefinito è binario: le contraddizioni escono come `not_supported` (ADR-0007).
- Le domande nella fonte possono prestare il loro presupposto a un'affermazione.
- Una domanda in inglese non trova un fatto salvato in italiano (ricerca per parole).
- Sul MCP la fonte la passa l'agente: verimem controlla che il fatto segua dal testo
  ricevuto, non che quel testo sia davvero dell'utente.
