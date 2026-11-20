# Role-play notes — Alex Morgan and Shreya

The full timed script is in [`talk_track.md`](talk_track.md). This page is the one-glance version.

## Who's in the room
| | Alex Morgan — business | Shreya — technical |
|---|---|---|
| Accountable for | Fraud loss, false-positive declines, customer experience | Authorization platform, data, security, model risk |
| Wants to hear | Dollars, risk, time to value | Latency, governance, integration, how good the model is |
| Chapters for them | 1 The case, 4 Ask the book | 2 Speed, 3 Governance |
| Close every answer with | The dollar or customer impact | What it means for the business |

## Rubric checklist
- **Demo setup:** agenda and time contract (slide 2), confirm priorities (slide 3), the problem (slide 4), "what you're about to see" with four things to watch (slide 5).
- **Tell-show-tell:** each of the four chapters opens with one sentence of what they'll see, shows it, and closes with one sentence of what it means. Slide 11 is the closing "tell" for the whole demo.
- **Value:** $7M fraud avoided + $4–6M recovered declines = $11–13M. 2 ms against a 50 ms budget. Always tied to the person who asked.
- **Delivery:** about 140 words a minute, pause after numbers, name the persona when switching, no filler.
- **Next steps:** three owners, three dates, and a confirmed date for the scoping session before hanging up.

## Opening questions (use their answers all call)
- Alex: "Is the bigger pressure right now fraud loss, or the good customers we're declining?"
- Shreya: "What would stop this from going near the authorization path on your side?"

## Hard objections
| Objection | Answer |
|---|---|
| Alex: "What if the model is wrong?" | Shadow mode first. It blocks nothing until fraud loss is down and false declines aren't up on your traffic. |
| Alex: "Why not our fraud vendor?" | The vendor scores the transaction on its own. The gap is your own Cyber takeover signal reaching the decision. You keep the data and the model. |
| Shreya: "How good is the model really?" | Holdout ROC-AUC about 0.77, modest precision and recall at 0.5. Not production-ready on synthetic data, which is exactly why the pilot is shadow mode with a threshold you tune. |
| Shreya: "Is 2 ms real?" | Measured from the deployed Databricks App to Lakebase, 20 lookups per page load. From a laptop over the internet it's about 80 ms, which is network distance, not the database. |
| Shreya: "Row-level security?" | Column masks and separate schemas today. A row filter on the combined table is next; it would have hidden the demo account from the app. |

## Time checks
7:00 in the demo · 19:00 recapping · 26:00 asking for next steps · 28:00 done.
If behind: drop the optional Genie question, then shorten chapter 3.
