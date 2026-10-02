# verimem-next — istruzioni per chi lavora su questo repo

Questo repo è la riscrittura da zero di verimem (vedi `docs/adr/0001-rewrite-from-scratch.md`).
Il vecchio repo `aureliocpr-ctrl/verimem` è un archivio di riferimento: da lì si prendono
idee, mai codice.

## Prima di fare qualunque cosa
1. Leggi `HANDOFF.md` (dove siamo) e `CHECKLIST.md` (cosa manca).
2. Prendi UNA voce della checklist. Scrivi nel messaggio iniziale il suo criterio di "fatto".
3. Lavora, poi verifica il criterio con il comando indicato.
4. Spunta la voce, aggiorna `HANDOFF.md`, fai commit con un messaggio che dice cosa e perché.

## Regole
- **Gli invarianti di `docs/DESIGN.md` §3 non si violano.** In particolare: `verified` si
  ottiene solo da un giudice-modello o da un umano; una sola funzione mappa il verdetto nello
  stato; niente chiamate di rete non richieste esplicitamente.
- **Numeri solo da comandi.** Nessuna cifra in README o docs che non esca da `verimem eval`,
  da `scripts/evals.sh`, da uno script in `scripts/research/` o da un test. Accanto al numero,
  il comando che lo produce.
- **Progetta su un insieme, misura su un altro.** Una modifica al verificatore o ad `ask` si
  disegna guardando un dataset e si giudica su uno scritto e messo in commit prima (come
  `datasets/qa-heldout.json`). Se non generalizza, si ritira e si scrive perché.
- **Test di comportamento.** Ogni cambiamento di comportamento ha un test che fallisce senza
  il cambiamento. Niente test che cercano frasi nel README.
- **Niente commenti-diario nel codice.** I commenti spiegano il perché in poche righe. Le
  decisioni vanno in un ADR breve in `docs/adr/`.
- **API pubblica in inglese.** Documenti per Aurelio in italiano.
- **Dipendenze**: il nucleo usa solo la libreria standard. torch/transformers solo
  nell'extra `nli`, mcp solo nell'extra `mcp`.
- **Un agente alla volta.** Niente sciami di agenti in parallelo sullo stesso ramo.

## Comandi
```
pip install -e ".[dev]"            # sviluppo, senza modelli
pip install -e ".[dev,nli,mcp]"    # tutto
ruff check src tests
pytest -m "not model"              # veloce, senza modelli (quello che gira in CI)
verimem warmup                     # scarica il giudice predefinito (1,16 GB, una volta)
VERIMEM_TEST_MODELS=1 pytest -m model   # con il modello vero
scripts/evals.sh                   # rigenera docs/eval/ e l'esempio di audit
```

## Chiedere ad Aurelio prima di
- cambiare licenza o pubblicare su PyPI;
- abilitare per default qualunque chiamata a servizi esterni;
- toccare il vecchio repo `verimem`;
- promettere numeri pubblici che non vengono da `docs/EVAL.md`.
