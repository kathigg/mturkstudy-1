| Rank | Architecture | Model | Prompt | Pol. P | Pol. R | Pol. F1 | Cat. F1 | Subcat. F1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | decision point | Decision point binary filter | P5 candidates + P2 adjudication + P4 label refinement | 0.537 | 0.756 | **0.628** | **0.560** | **0.531** |
| 2 | decision point | Decision point full | P5 candidates + P2 adjudication + P4 label refinement | 0.529 | 0.744 | 0.618 | 0.531 | 0.483 |
| 3 | single small model | GPT-5 mini | P5 human aligned | 0.486 | 0.791 | 0.602 | 0.522 | 0.478 |
| 4 | OG adjudication | GPT-5.1 + Gemini Pro + Claude Sonnet -> Claude Opus | P2 Bagozzi | 0.486 | 0.779 | 0.598 | 0.527 | 0.473 |
| 5 | single small model | GPT-5 mini | P1 default | 0.508 | 0.721 | 0.596 | 0.490 | 0.442 |
| 6 | OG adjudication | GPT-5.1 + Gemini Pro + Claude Sonnet -> Claude Opus | P5 human aligned | 0.508 | 0.698 | 0.588 | 0.520 | 0.480 |
| 7 | single strong model | Gemini 3.1 Pro Preview | P5 human aligned | 0.523 | 0.651 | 0.580 | 0.518 | 0.497 |
| 8 | single strong model | Gemini 3.1 Pro Preview | P2 Bagozzi | 0.541 | 0.616 | 0.576 | 0.533 | 0.489 |
| 9 | decision point | Decision point candidate union | P5 candidates + P2 adjudication + P4 label refinement | 0.427 | **0.849** | 0.568 | 0.506 | 0.482 |
| 10 | single small model | GPT-5 mini | P2 Bagozzi | 0.441 | 0.779 | 0.563 | 0.471 | 0.387 |
| 11 | single small model | GPT-5 mini | P3 short spans | 0.466 | 0.709 | 0.562 | 0.498 | 0.461 |
| 12 | OG adjudication | GPT-5.1 + Gemini Pro + Claude Sonnet -> Claude Opus | P1 default | 0.461 | 0.686 | 0.551 | 0.458 | 0.411 |
| 13 | single small model | GPT-5 mini | P4 boundary | 0.467 | 0.663 | 0.548 | 0.452 | 0.394 |
| 14 | single small model | Gemini 3.1 Flash Lite | P5 human aligned | 0.470 | 0.640 | 0.542 | 0.433 | 0.414 |
| 15 | single small model | Gemini 3.1 Flash Lite | P2 Bagozzi | 0.491 | 0.605 | 0.542 | 0.385 | 0.323 |
| 16 | single strong model | Claude Sonnet 5 | P5 human aligned | 0.438 | 0.698 | 0.538 | 0.493 | 0.457 |
| 17 | OG adjudication | GPT-5.1 + Gemini Pro + Claude Sonnet -> Claude Opus | P4 boundary | 0.427 | 0.651 | 0.516 | 0.479 | 0.452 |
| 18 | OG adjudication | GPT-5.1 + Gemini Pro + Claude Sonnet -> Claude Opus | P3 short spans | 0.442 | 0.616 | 0.515 | 0.447 | 0.417 |
| 19 | single small model | Gemini 3.1 Flash Lite | P1 default | 0.463 | 0.581 | 0.515 | 0.392 | 0.351 |
| 20 | single strong model | Claude Sonnet 5 | P2 Bagozzi | 0.391 | 0.733 | 0.510 | 0.429 | 0.364 |
| 21 | single strong model | Claude Sonnet 5 | P1 default | 0.403 | 0.651 | 0.498 | 0.418 | 0.373 |
| 22 | single strong model | Gemini 3.1 Pro Preview | P1 default | 0.448 | 0.500 | 0.473 | 0.451 | 0.418 |
| 23 | single strong model | Gemini 3.1 Pro Preview | P4 boundary | 0.426 | 0.500 | 0.460 | 0.428 | 0.406 |
| 24 | single small model | Gemini 3.1 Flash Lite | P3 short spans | 0.413 | 0.500 | 0.453 | 0.347 | 0.316 |
| 25 | single strong model | GPT-5.1 | P1 default | 0.323 | 0.733 | 0.448 | 0.370 | 0.306 |
| 26 | single strong model | Claude Sonnet 5 | P4 boundary | 0.376 | 0.512 | 0.433 | 0.394 | 0.365 |
| 27 | single strong model | GPT-5.1 | P2 Bagozzi | 0.307 | 0.721 | 0.431 | 0.368 | 0.319 |
| 28 | single strong model | GPT-5.1 | P4 boundary | 0.314 | 0.686 | 0.431 | 0.358 | 0.314 |
| 29 | single small model | Gemini 3.1 Flash Lite | P4 boundary | 0.388 | 0.465 | 0.423 | 0.339 | 0.307 |
| 30 | single strong model | Gemini 3.1 Pro Preview | P3 short spans | 0.390 | 0.453 | 0.419 | 0.419 | 0.398 |
| 31 | single strong model | Claude Sonnet 5 | P3 short spans | 0.373 | 0.442 | 0.404 | 0.351 | 0.351 |
| 32 | single strong model | GPT-5.1 | P5 human aligned | 0.296 | 0.640 | 0.404 | 0.331 | 0.324 |
| 33 | single strong model | GPT-5.1 | P3 short spans | 0.247 | 0.500 | 0.331 | 0.277 | 0.246 |
| 34 | single small model | Claude Haiku 4.5 | P5 human aligned | 0.315 | 0.326 | 0.320 | 0.297 | 0.286 |
| 35 | single small model | Claude Haiku 4.5 | P4 boundary | 0.281 | 0.291 | 0.286 | 0.274 | 0.263 |
| 36 | single small model | Claude Haiku 4.5 | P3 short spans | 0.281 | 0.291 | 0.286 | 0.251 | 0.240 |
| 37 | single small model | Claude Haiku 4.5 | P2 Bagozzi | 0.225 | 0.233 | 0.229 | 0.217 | 0.206 |
| 38 | single small model | Claude Haiku 4.5 | P1 default | 0.191 | 0.198 | 0.194 | 0.183 | 0.183 |
