"""
Milestone 4 signal verification.
Tests both signals independently, then the combined scorer, on all four
canonical inputs. Run this before restarting Flask.

Usage:
    python3 test_signals.py
"""

import os, sys
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from app import get_llm_score, get_style_score, get_combined_score, _get_attribution

TEST_INPUTS = [
    (
        "clearly_ai",
        "Artificial intelligence represents a transformative paradigm shift in modern society. "
        "It is important to note that while the benefits of AI are numerous, it is equally "
        "essential to consider the ethical implications. Furthermore, stakeholders across "
        "various sectors must collaborate to ensure responsible deployment of these technologies "
        "in a manner that prioritises human well-being and sustainable progress for all.",
    ),
    (
        "clearly_human",
        "ok so i finally tried that new ramen place downtown and honestly? "
        "underwhelming. the broth was fine but they put WAY too much sodium in it and "
        "i was thirsty for like three hours after. my friend got the spicy version and "
        "said it was better. probably won't go back unless someone drags me there. "
        "also the seating situation was weird — you share a table with strangers which "
        "i get is a vibe but it just felt cramped.",
    ),
    (
        "borderline_formal_human",
        "The relationship between monetary policy and asset price inflation has been "
        "extensively studied in the literature. Central banks face a fundamental tension "
        "between their mandate for price stability and the unintended consequences of "
        "prolonged low interest rates on equity and real estate valuations. This dynamic "
        "has become especially pronounced in the post-2008 environment, where unconventional "
        "policy tools have reshaped the transmission mechanism in ways that are still debated.",
    ),
    (
        "borderline_edited_ai",
        "I've been thinking a lot about remote work lately. There are genuine tradeoffs — "
        "flexibility and no commute on one side, isolation and blurred work-life boundaries "
        "on the other. Studies show productivity varies widely by individual and role type. "
        "Personally, I find the lack of hallway conversations harder to replace than I expected. "
        "It turns out a lot of my best ideas came from interruptions I used to resent.",
    ),
]

def main():
    print(f"\n{'Label':<28} {'llm':>6} {'style':>6} {'combined':>9} {'attribution':>14}")
    print("─" * 70)

    for label, text in TEST_INPUTS:
        llm   = get_llm_score(text)
        style = get_style_score(text)
        comb  = get_combined_score(llm, style["style_score"])
        attr  = _get_attribution(comb)
        print(f"{label:<28} {llm:>6.3f} {style['style_score']:>6.3f} {comb:>9.4f} {attr:>14}")
        print(f"  sub-scores → ttr={style['ttr']:.3f}  sent_var={style['sent_variance']:.2f}  punct={style['punct_density']:.3f}")

    print()
    print("Expected:")
    print("  clearly_ai           → combined ≥ 0.65  (likely_ai)")
    print("  clearly_human        → combined < 0.35  (likely_human)")
    print("  borderline_*         → 0.35–0.65        (uncertain)")
    print()
    print("If clearly_ai is below 0.65, check llm_score first.")
    print("If clearly_human is above 0.35, check style sub-scores — sent_variance and ttr.")

if __name__ == "__main__":
    main()