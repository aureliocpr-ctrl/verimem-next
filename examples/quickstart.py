"""The README quickstart. Run: python examples/quickstart.py (after `verimem warmup`)."""

from verimem import Memory

memory = Memory(":memory:")  # Memory("memory.db") keeps it in a file

source = ("User: I moved from Rome to Milan in 2021 for a job at a bank. "
          "I still go back to Rome most weekends.")

for claim in ["The user moved to Milan in 2021.",
              "The user works as a financial analyst.",
              "The user moved to Milan in 2019."]:
    result = memory.remember(claim, source=source, author="user")
    print(f"{result.status.value:<12} {claim}  ({result.verdict.reason})")

for question in ["When did the user move to Milan?",
                 "Which city did the user move to?",
                 "What is the name of the user's dog?"]:
    answer = memory.ask(question)
    print(f"\n{question}")
    if answer.abstained:
        print(f"  not in memory: {answer.reason}")
    for hit in answer.facts:
        print(f"  {hit.fact.text}  (relevance {hit.score:.2f})")
        print(f"  evidence: {hit.fact.evidence.text!r}")
