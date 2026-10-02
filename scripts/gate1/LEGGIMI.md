# Cancello 1: il giudice regge sui tuoi dati?

Domanda: sui tuoi dati, il giudice ferma le memorie che la fonte non dice senza buttare
quelle vere? Se nessun giudice locale ci riesce, la promessa del prodotto non regge in
locale e ci si ferma (regola in `docs/business/BUSINESS.md`). Costo: zero euro, mezza giornata.

La regola di decisione è scritta qui **prima** di vedere i numeri e non si ridiscute dopo:

> Un giudice passa se, nella colonna "Held-out" di `verimem eval` (soglia scelta su metà
> delle coppie e misurata sull'altra metà, 200 volte), perde al massimo il 10% delle
> memorie vere (`true lost` ≤ 10%) e ammette al massimo il 10% di quelle non dette
> (`N admitted` ≤ 10%), con almeno 50 coppie `S` e 50 coppie `N`.

## 1. Esporta le coppie (2 minuti)

```
python scripts/gate1/esporta_coppie.py
```

Legge `~/.engram/semantic/semantic.db` (lo store della versione 0.7) **in sola lettura** e
scrive `coppie_da_etichettare.csv`: 300 coppie (fonte, fatto) a caso fra i fatti che hanno
un estratto di fonte salvato (`grounding_span`, dai fatti scritti dall'8 agosto 2026). Il
punteggio del vecchio giudice non viene esportato, apposta. Opzioni: `--db`, `--n`, `--out`.

Nota: `grounding_span` è il pezzo di fonte che il vecchio sistema ha scelto come più
pertinente, non la fonte intera. Etichetta guardando solo quel pezzo.

## 2. Se le memorie non dette sono poche, aggiungine (30-60 minuti)

Servono almeno 50 coppie per tipo. Prendi 30-40 testi tuoi brevi (messaggi, note, appunti),
in italiano e in inglese; chiedi a un LLM qualsiasi di estrarne 5 fatti ciascuno "come
farebbe una memoria"; metti ogni coppia in una riga (`fonte` = il testo, `fatto` = il fatto
estratto). Le estrazioni degli LLM contengono da sole dettagli non detti: è il caso che il
prodotto deve fermare.

## 3. Etichetta (2-3 ore per 300 coppie)

Apri il CSV con Excel e compila:

- `lingua`: IT o EN
- `etichetta`: `S` la fonte lo dice, o lo implica senza margine di dubbio; `N` plausibile, ma
  la fonte non lo dice; `C` la fonte dice il contrario
- `note`: il motivo, quando hai dubbi

Non guardare nessun punteggio mentre etichetti. Nel dubbio fra S e N scegli N. Se puoi, fai
etichettare 50 righe anche a un'altra persona: se siete in disaccordo su più di una riga su
sette, chiarite le definizioni prima di andare avanti. Salva come `coppie_etichettate.csv`
(separatore punto e virgola: `verimem` legge le intestazioni italiane).

## 4. Misura (10-30 minuti di CPU)

```
verimem eval coppie_etichettate.csv --markdown cancello1-bge-m3.md
```

Altri giudici gratuiti, per confronto (il primo `warmup` scarica il modello):

```
verimem warmup --judge hf:Horizon-Labs/hallucination-guard-base
verimem eval coppie_etichettate.csv --judge hf:Horizon-Labs/hallucination-guard-base --markdown cancello1-horizon.md
```

Sui 40 casi di `datasets/review-cases.csv` funzionano anche
`hf:MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` e
`hf:MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`, ma entrambi sono addestrati
anche su ANLI, che ha una licenza non commerciale: da chiarire prima di usarli in un prodotto
a pagamento. Il giudice predefinito (bge-m3-zeroshot-v2.0-c, MIT) dichiara nella sua scheda
dati di addestramento usabili commercialmente; Horizon (Apache-2.0) è addestrato su RAGTruth
e WANLI, licenze dei dati da verificare. `--judge lexical` è il controllo: se fa quasi come i
modelli, il set è troppo facile.

## 5. Decidi con la regola scritta sopra

- **Nessun giudice passa**: ci si ferma sul prodotto; set e risultati si possono pubblicare
  come lavoro di ricerca.
- **Uno o più passano**: si sceglie il migliore con licenza pulita, e si calibra la policy
  sui tuoi dati:

```
verimem calibrate coppie_etichettate.csv --out policy-cancello1.json --version 1.0.0-cancello1
```

La nuova policy porta con sé da dove viene (dataset, coppie, tassi misurati). Diventa la
policy predefinita solo con un commit che la sostituisce a `src/verimem/policies/default.json`
e aggiorna `docs/EVAL.md`.
