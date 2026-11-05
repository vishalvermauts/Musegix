# Musegix demo narration (about 2 minutes 30 seconds)

Voice: Ron Sage - Warm, Soulful & Conversation (ElevenLabs)
Demo project: TableTide (restaurant reservations)

## 1. The problem (15 s)
AI coding tools resend the whole conversation and the whole project on every step. Every step costs tokens, money and time, and most of what gets resent is already old.

## 2. The architecture (30 s)
Musegix sits between the browser app builder and Meta's models. Every request passes through three engines before it reaches the model: Ysolveth decides which model should handle it, PolyFabric decides what context to send, and Veylqora decides what the change affects.

## 3. Engine one: Ysolveth, routing (25 s)
Ysolveth is an on-device routing model. It classifies each request on the CPU in a few milliseconds, with no extra API call. Simple edits go to a cheaper, faster model. Harder work goes to a stronger one.

## 4. Engine two: PolyFabric, saving tokens (30 s)
PolyFabric is where the tokens are saved. It keeps the files a request needs, and it shortens old tool output: earlier file reads and command logs. In our test runs, old tool output was cut by about 95 percent. The saving on the project files depends on project size.

## 5. Engine three: Veylqora, impact (20 s)
Veylqora fingerprints every function and component. When an exported symbol changes, it lists the files that still depend on it, so the model does not have to rediscover them.

## 6. One build, with the engines shown (20 s)
Here is TableTide, built from one sentence. Above the reply, three boxes show the engines at work: the tier Ysolveth chose and the model, the tokens PolyFabric sent after trimming, and the stale-symbol status from Veylqora.

## 7. Edits, where the saving and speed show (30 s)
Now two edits. A trivial colour change goes to the cheaper model, and it finishes in seconds. A multi-file edit, a new button that updates shared state across two pages, takes longer, and the boxes show how much context it needed and how much was trimmed.

## 8. The numbers and their limits (15 s)
Old tool output cut by about 95 percent across our test runs. Routing about 80 percent accurate on our own test prompts, and weaker on hard tasks. The project-file saving depends on project size. These are our measurements, not a general guarantee.

## 9. Closing (15 s)
Three engines, three savings: fewer tokens, lower cost, and faster edits. Musegix is an early prototype, and the numbers are shown on screen.
