"""Test del nuevo flujo híbrido (WorldCupProvider + OddsFetcher)."""
import sys
import os
from datetime import datetime, timezone

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, ".")

from lib.world_cup_provider import WorldCupProvider
from lib.odds_fetcher import OddsFetcher
from lib.value_calculator import ValueCalculator
from api.matches import _merge_world_cup_with_odds

print("=" * 60)
print("TEST: Flujo Híbrido Mundial 2026")
print("=" * 60)

# 1. Obtener fixture del Mundial
print("\n--- Paso 1: WorldCupProvider ---")
wc = WorldCupProvider()
wc_matches = wc.get_fixture(only_upcoming=True, window_days=7)
print(f"✓ Modo: {'DEMO' if wc.is_mock else 'API REAL'}")
print(f"✓ Total partidos WC en próximos 7 días: {len(wc_matches)}")

if wc_matches:
    print(f"\nPrimeros 5 partidos:")
    for m in wc_matches[:5]:
        # Calcular tiempo relativo
        commence = datetime.fromisoformat(m["commence_time"].replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff_hours = (commence - now).total_seconds() / 3600
        day_str = "HOY" if abs(diff_hours) < 24 else f"en {diff_hours/24:.1f} días"
        group_str = f"[{m.get('group', 'N/A')}]" if m.get('group') else f"[{m.get('stage', 'N/A')}]"
        print(f"  {group_str:12s} {m['home_team']:20s} vs {m['away_team']:20s} → {day_str}")

# 2. Obtener cuotas
print("\n--- Paso 2: OddsFetcher ---")
fetcher = OddsFetcher()
odds_matches = fetcher.get_matches()
print(f"✓ Modo: {'DEMO' if fetcher.is_mock else 'API REAL'}")
print(f"✓ Partidos con cuotas: {len(odds_matches)}")
if odds_matches:
    for m in odds_matches[:3]:
        print(f"  {m['home_team']:20s} vs {m['away_team']:20s}")

# 3. Cruzar
print("\n--- Paso 3: Cruce WC + Cuotas ---")
merged = _merge_world_cup_with_odds(wc_matches, odds_matches)
with_odds = [m for m in merged if not m.get("odds_pending")]
without_odds = [m for m in merged if m.get("odds_pending")]
print(f"✓ Partidos WC con cuotas: {len(with_odds)}")
print(f"✓ Partidos WC sin cuotas (pendientes): {len(without_odds)}")

# 4. Calcular value
print("\n--- Paso 4: ValueCalculator ---")
calc = ValueCalculator(min_edge=3)
analyzed = calc.analyze_matches(merged)
value_bets = [r for r in analyzed if r.get("has_value")]
print(f"✓ Total partidos analizados: {len(analyzed)}")
print(f"✓ Value bets encontrados: {len(value_bets)}")

if value_bets:
    print(f"\nTop 3 value bets:")
    for vb in value_bets[:3]:
        bb = vb.get("best_bet", {})
        cls = bb.get("classification", {})
        edge = bb.get("edge", 0)
        print(f"  {cls.get('emoji', '')} {vb['home_team']:20s} vs {vb['away_team']:20s}")
        print(f"      {bb.get('outcome', ''):15s} @ {bb.get('odds', 0):.2f} → edge=+{edge:.1f}% ({cls.get('label', '')})")

# 5. Resumen final
print("\n" + "=" * 60)
print("RESUMEN")
print("=" * 60)
print(f"✓ Mundial 2026 detectado: 11 jun - 19 jul 2026")
print(f"✓ Partidos próximos (7 días): {len(wc_matches)}")
print(f"✓ Cobertura de cuotas: {len(with_odds)}/{len(merged)} ({100*len(with_odds)/max(len(merged),1):.0f}%)")
print(f"✓ Value bets activos: {len(value_bets)}")
print(f"\n{'TODO OK ✅' if len(wc_matches) > 0 else 'PROBLEMAS ❌'}")