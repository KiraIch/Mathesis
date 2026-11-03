import Mathlib
namespace MathesisHard
theorem lean_ineq_cube_sum_zero_sixth : ∀ x y z : ℝ, x + y + z = 0 → 54 * (x * y * z) ^ 2 ≤ (x ^ 2 + y ^ 2 + z ^ 2) ^ 3 := by
  intro x y z h
  have hz : z = -x - y := by linarith
  subst hz
  nlinarith [sq_nonneg ((x - y) * (2 * x + y) * (x + 2 * y))]
end MathesisHard
