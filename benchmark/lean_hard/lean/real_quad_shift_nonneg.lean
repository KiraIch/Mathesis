import Mathlib
namespace MathesisHard
theorem lean_real_quad_shift_nonneg : ∀ x : ℝ, 0 ≤ x ^ 2 - 4 * x + 4 := by
  intro x
  nlinarith [sq_nonneg (x - 2)]
end MathesisHard
