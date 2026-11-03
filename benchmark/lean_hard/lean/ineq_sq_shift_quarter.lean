import Mathlib
namespace MathesisHard
theorem lean_ineq_sq_shift_quarter : ∀ x : ℝ, x ≤ x ^ 2 + 1 / 4 := by
  intro x
  nlinarith [sq_nonneg (x - 1 / 2)]
end MathesisHard
