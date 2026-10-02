# Rapporto di affidabilità della memoria

## Sintesi

- **32** memorie confrontate con il testo da cui sono state estratte.
- **13** sostenute dalla fonte.
- **16** non sostenute dalla loro fonte: **53% (36%-70%)** sulle 30 giudicabili.
- **7** aggiungono un numero, un importo o una data che la fonte non contiene.
- **1** sostenute debolmente (da rivedere, non contate come errori).
- **2** senza fonte, quindi non verificabili.

## Cosa significa

Una memoria è *non sostenuta* quando il testo da cui viene non la dice. Di solito è un dettaglio aggiunto da un LLM durante l'estrazione: plausibile, spesso verosimile, e poi restituito come se l'utente l'avesse detto davvero.

## Esempi di memorie non sostenute

- **Il ritardo del tecnico è costato a Termoidraulica Alfa 4.000 euro.**  
  numeri o date assenti nella fonte: 4.000  
  _passaggio più vicino nella fonte:_ “Paolo Ferri: L'ultima volta il vostro tecnico è arrivato con due giorni di ritardo e abbiamo dovuto fermare un cantiere. Non deve ripetersi.”

- **Ortofrutta Gamma ha un budget di 20.000 euro per il modulo magazzino.**  
  numeri o date assenti nella fonte: 20.000  
  _passaggio più vicino nella fonte:_ “Nota della chiamata con Marta Villa (Ortofrutta Gamma): gestiscono ancora gli ordini con fogli Excel e vorrebbero una demo del modulo magazzino prima di decidere. Budget non ancora definito.”

- **Ortofrutta Gamma ha già scelto il nostro modulo magazzino.**  
  la fonte non lo dice (sostegno massimo p=0.00)  
  _passaggio più vicino nella fonte:_ “Nota della chiamata con Marta Villa (Ortofrutta Gamma): gestiscono ancora gli ordini con fogli Excel e vorrebbero una demo del modulo magazzino prima di decidere.”

- **The user is strictly vegan.**  
  la fonte non lo dice (sostegno massimo p=0.00)  
  _passaggio più vicino nella fonte:_ “User: I switched to a vegetarian diet last month, but I still eat fish now and then.”

- **La riunione per la firma con lo Studio Zefiro & Partners si terrà online.**  
  la fonte non lo dice (sostegno massimo p=0.00)  
  _passaggio più vicino nella fonte:_ “Email di Giulia Zefiro (ufficio legale, Studio Zefiro & Partners), 14 febbraio: confermo che la riunione per la firma è spostata a giovedì 20 febbraio alle 15:00, presso la nostra sede di via Solferino.”

- **Termoidraulica Alfa chiede uno sconto del 15% sul canone.**  
  numeri o date assenti nella fonte: 15%  
  _passaggio più vicino nella fonte:_ “Cliente: Buongiorno, sono Paolo Ferri, responsabile acquisti di Termoidraulica Alfa.”

- **Termoidraulica Alfa avrà 15 tecnici entro l'estate.**  
  numeri o date assenti nella fonte: 15  
  _passaggio più vicino nella fonte:_ “Paolo Ferri: Al momento abbiamo 12 tecnici sul campo e ognuno usa la vostra app sul tablet. Entro l'estate ne assumiamo altri tre.”

- **The user returns from Lisbon on the 19th.**  
  numeri o date assenti nella fonte: 19th  
  _passaggio più vicino nella fonte:_ “User: I'm flying to Lisbon on the 14th for the conference, back on the 18th.”

- **Logistica Delta usa Windows Server 2022.**  
  numeri o date assenti nella fonte: 2022  
  _passaggio più vicino nella fonte:_ “Davide (IT di Logistica Delta): il server lo teniamo in casa, niente cloud, è una regola del gruppo.”

- **The user's team is fully remote.**  
  la fonte non lo dice (sostegno massimo p=0.01)  
  _passaggio più vicino nella fonte:_ “User: Our team moved standup from 9:00 to 10:00 because half of us are on Lisbon time now.”

## Limiti di questo rapporto

I verdetti vengono da un giudice automatico (hf:MoritzLaurer/bge-m3-zeroshot-v2.0-c@705510dfe0f3), con la policy 0.9.0-provisional. Il giudice sbaglia in entrambe le direzioni; la sua calibrazione è descritta sotto. Prima di agire sui numeri, rivedete un campione delle righe segnalate (`review.csv` ha una colonna apposta). Il giudice controlla la coerenza con la fonte, non la verità: una fonte sbagliata fa sembrare sostenuta una memoria sbagliata.

`review.csv` elenca tutte le memorie giudicabili con la loro fonte, raggruppate per verdetto (prima quelle segnalate) e in ordine casuale dentro ogni gruppo. Leggetene alcune dall'inizio di ogni gruppo, scrivete sì o no nella colonna `stated_by_source`, poi lanciate `verimem audit-review` su questa cartella per una stima controllata da una persona.

### Calibrazione del giudice

**verifier**

- status: provisional
- dataset: datasets/review-cases.csv (40 pairs written by Claude)
- note: support 0.5 / uncertain 0.2 separate the review cases perfectly; to be replaced by a calibration on 200+ real pairs (CHECKLIST phase 8)

**relevance**

- status: provisional
- dataset: datasets/qa-mini.json (50 questions written by Claude)
- template: en/it 'This text answers the question: ...'
- threshold: 0.4
- measured: 17/25 answerable questions answered with the right fact, 8 wrong abstentions; 25/25 unanswerable questions abstained, 0 false answers (verimem eval-ask datasets/qa-mini.json)

Generato da verimem 0.9.0.dev0 il 2026-10-02 12:54 UTC.
