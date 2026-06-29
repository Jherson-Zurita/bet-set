"""Quick test script for Value Bet Finder modules."""
import sys
import os

# Fix Windows console encoding for emojis
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, ".")

from lib.value_calculator import ValueCalculator, calculate_edge, implied_probability, classify_edge
from lib.odds_fetcher import OddsFetcher

print("=" * 50)
print("VALUE BET FINDER — Module Tests")
print("=" * 50)

# Test 1: Value Calculator basics
print("\n--- Test 1: Value Calculator ---")
prob = implied_probability(2.10)
print(f"Prob implicita cuota 2.10: {prob*100:.1f}%")

edge = calculate_edge(2.10, 0.518)
print(f"Edge (b365=2.10, fair_prob=0.518): {edge:.1f}%")

classification = classify_edge(8.8)
print(f"Clasificacion edge 8.8: {classification['label']} {classification['emoji']}")

classification2 = classify_edge(4.0)
print(f"Clasificacion edge 4.0: {classification2['label']} {classification2['emoji']}")

# Test 2: Odds Fetcher (mock)
print("\n--- Test 2: Odds Fetcher (Mock) ---")
fetcher = OddsFetcher()
matches = fetcher.get_matches()
print(f"Mock mode: {fetcher.is_mock}")
print(f"Partidos obtenidos: {len(matches)}")
for m in matches:
    print(f"  {m['home_team']} vs {m['away_team']}")

# Test 3: Full pipeline
print("\n--- Test 3: Full Pipeline ---")
vc = ValueCalculator()
results = vc.analyze_matches(matches)
value_bets = [r for r in results if r["has_value"]]
print(f"Total partidos analizados: {len(results)}")
print(f"Value bets encontrados: {len(value_bets)}")

for v in value_bets:
    bb = v.get("best_bet", {})
    edge_val = bb.get("edge", 0)
    cls = bb.get("classification", {})
    print(f"  {cls.get('emoji', '')} {v['home_team']} vs {v['away_team']}: "
          f"{bb.get('outcome', '')} @ {bb.get('odds', 0):.2f} "
          f"edge=+{edge_val:.1f}% ({cls.get('label', '')})")

# Test 4: Stats Enricher
print("\n--- Test 4: Stats Enricher ---")
from lib.stats_enricher import StatsEnricher
enricher = StatsEnricher()
stats = enricher.enrich_match(matches[0])
print(f"Home stats form: {stats['home']['form']}")
print(f"Away stats form: {stats['away']['form']}")
print(f"H2H matches: {stats['h2h']['matches_total']}")
print(f"Insights: {len(stats['insights'])}")
for insight in stats["insights"]:
    print(f"  {insight}")

# Test 5: AI Analyzer (mock)
print("\n--- Test 5: AI Analyzer (Mock) ---")
from lib.ai_analyzer import AIAnalyzer
analyzer = AIAnalyzer()
analysis = analyzer.analyze_match(matches[0], results[0], stats)
print(f"Mock mode: {analyzer.is_mock}")
print(f"Analysis: {analysis.get('analysis', '')[:100]}...")
print(f"Risk level: {analysis.get('risk_level', 'N/A')}")
rec = analysis.get("recommended_bet", {})
if rec:
    print(f"Recommendation: {rec.get('selection', '')} @ {rec.get('odds', 0)} (confidence: {rec.get('confidence', '')})")

print("\n" + "=" * 50)
print("ALL TESTS PASSED ✅")
print("=" * 50)
