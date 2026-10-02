# Passaggio di consegne

Ultimo aggiornamento: 2026-10-02, sessione cloud di Claude (riscrittura da zero).

## Dove siamo

Fasi 1-7 della [checklist](CHECKLIST.md) fatte (tranne versione e PyPI): verificatore,
memoria, lettura con astensione, valutazione, rapporto di affidabilità con ciclo di
revisione, CLI e server MCP, pacchetto provato in ambienti puliti. Il codice è su
`aureliocpr-ctrl/verimem-next` (pubblico).

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

Suite: `pytest -m "not model"` → 138 test passati (con mcp 1.30 e con mcp 2.2);
`ruff check src tests` pulito; `VERIMEM_TEST_MODELS=1 pytest -m model` → 2 passati
(ultima esecuzione: 2026-10-02).

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

1. **Per Aurelio, prima di vendere: Cancello 1** con `scripts/gate1/LEGGIMI.md` (mezza
   giornata di etichette). Decide se il giudice regge sui dati veri e calibra le soglie.
2. **Per Aurelio, in parallelo**: scegliere il prezzo dell'audit e i primi 30 contatti (le
   bozze dell'offerta e dei messaggi sono nel materiale commerciale consegnato a parte).
3. **Codice**: la voce aperta più utile è "Pertinenza migliore" (fase 3): `ask` si astiene
   troppo. Prima di provare qualunque cosa, scrivere e mettere in commit un terzo insieme di
   domande.

## Decisioni aperte per Aurelio

1. **Il materiale commerciale** (piano con prezzi ipotizzati e criteri di stop, offerta,
   manuale di consegna, messaggi di contatto, post) non è in questo repository pubblico: è
   stato tolto dalla storia prima del primo push e consegnato a parte. Se lo vuoi qui, o in
   un repository privato, si aggiunge con un commit.
2. **PyPI**: pubblicare questa versione con il nome `verimem` (oggi installa la 0.7.x)?
3. Più avanti: rinominare questo repository in `verimem` e archiviare il vecchio?

## Problemi noti

- Il giudice predefinito è binario: le contraddizioni escono come `not_supported` (ADR-0007).
- Le domande nella fonte possono prestare il loro presupposto a un'affermazione.
- Una domanda in inglese non trova un fatto salvato in italiano (ricerca per parole).
- Sul MCP la fonte la passa l'agente: verimem controlla che il fatto segua dal testo
  ricevuto, non che quel testo sia davvero dell'utente.
