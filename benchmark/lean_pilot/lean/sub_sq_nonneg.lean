import Mathlib
namespace MathesisPilot
theorem lean_sub_sq_nonneg : ∀ (a b : ℝ), 0 ≤ (a - b) ^ 2 := by
  intro a
  intro b
  have h : 0 ≤ (a - b) ^ 2 := sq_nonneg (a - b)
  exact h
end MathesisPilot
