import Mathlib
namespace MathesisHard
theorem lean_real_cube_ge_double_sq : ∀ x : ℝ, 0 < x → 2 * x ^ 2 ≤ x ^ 3 + x := by
  intro x hx
  nlinarith [mul_nonneg hx.le (sq_nonneg (x - 1))]
end MathesisHard
