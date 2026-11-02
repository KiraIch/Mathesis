import Mathlib
namespace MathesisPilot
theorem lean_sq_nonneg : ∀ (a : ℝ), 0 ≤ a ^ 2 := by
  intro a
  have h : 0 ≤ a ^ 2 := sq_nonneg a
  exact h
end MathesisPilot
