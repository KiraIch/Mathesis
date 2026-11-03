import Mathlib
namespace MathesisHard
theorem lean_ineq_quartic_shift_nonneg : ∀ x : ℝ, 0 ≤ x ^ 4 - 2 * x ^ 2 + 1 := by
  intro x
  nlinarith [sq_nonneg (x ^ 2 - 1)]
end MathesisHard
