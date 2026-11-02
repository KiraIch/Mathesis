import Mathlib
namespace MathesisPilot
theorem lean_abs_nonneg : ∀ (a : ℝ), 0 ≤ |a| := by
  intro a
  exact abs_nonneg a
end MathesisPilot
