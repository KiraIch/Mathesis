import Mathlib
namespace MathesisHard
theorem lean_ineq_xy_quarter_bound : ∀ x y : ℝ, x * y ≤ x ^ 2 / 4 + y ^ 2 := by
  intro x y
  nlinarith [sq_nonneg (x - 2 * y)]
end MathesisHard
