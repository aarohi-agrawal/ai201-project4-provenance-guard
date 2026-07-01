"""
Run this BEFORE wiring the LLM signal into the endpoint.
It calls get_llm_score() directly on the four canonical test inputs and
prints each score so you can verify the signal is behaving sensibly.

Usage:
    python test_llm_signal.py
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Make sure app.py is importable from the same directory
sys.path.insert(0, os.path.dirname(__file__))
from app import get_llm_score

TEST_INPUTS = [
    (
        "clearly_ai",
        (
            "Artificial intelligence represents a transformative paradigm shift in modern society. "
            "It is important to note that while the benefits of AI are numerous, it is equally "
            "essential to consider the ethical implications. Furthermore, stakeholders across "
            "various sectors must collaborate to ensure responsible deployment of these technologies "
            "in a manner that prioritises human well-being and sustainable progress for all."
        ),
    ),
    (
        "clearly_human",
        (
            "ok so i finally tried that new ramen place downtown and honestly? "
            "underwhelming. the broth was fine but they put WAY too much sodium in it and "
            "i was thirsty for like three hours after. my friend got the spicy version and "
            "said it was better. probably won't go back unless someone drags me there. "
            "also the seating situation was weird — you share a table with strangers which "
            "i get is a vibe but it just felt cramped."
        ),
    ),
    (
        "borderline_formal_human",
        (
            "The relationship between monetary policy and asset price inflation has been "
            "extensively studied in the literature. Central banks face a fundamental tension "
            "between their mandate for price stability and the unintended consequences of "
            "prolonged low interest rates on equity and real estate valuations. This dynamic "
            "has become especially pronounced in the post-2008 environment, where unconventional "
            "policy tools have reshaped the transmission mechanism in ways that are still debated."
        ),
    ),
    (
        "borderline_edited_ai",
        (
            "I've been thinking a lot about remote work lately. There are genuine tradeoffs — "
            "flexibility and no commute on one side, isolation and blurred work-life boundaries "
            "on the other. Studies show productivity varies widely by individual and role type. "
            "Personally, I find the lack of hallway conversations harder to replace than I expected. "
            "It turns out a lot of my best ideas came from interruptions I used to resent."
        ),
    ),
]


def main():
    print(f"{'Label':<28} {'llm_score':>10}  {'attribution':>14}")
    print("-" * 56)
    for label, text in TEST_INPUTS:
        score = get_llm_score(text)
        if score < 0.35:
            attribution = "likely_human"
        elif score < 0.65:
            attribution = "uncertain"
        else:
            attribution = "likely_ai"
        print(f"{label:<28} {score:>10.4f}  {attribution:>14}")

    print()
    print("Expected rough outcomes:")
    print("  clearly_ai            → score ≥ 0.65  (likely_ai)")
    print("  clearly_human         → score < 0.35  (likely_human)")
    print("  borderline_formal_*   → 0.35–0.65     (uncertain)")
    print("  borderline_edited_ai  → 0.35–0.65     (uncertain)")


if __name__ == "__main__":
    main()