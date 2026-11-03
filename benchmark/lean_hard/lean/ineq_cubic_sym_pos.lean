import Mathlib
namespace MathesisHard
theorem lean_ineq_cubic_sym_pos : ∀ x y : ℝ, 0 < x → 0 < y → x ^ 2 * y + x * y ^ 2 ≤ x ^ 3 + y ^ 3 := by
  intro x y hx hy
  nlinarith [mul_nonneg (add_pos hx hy).le (sq_nonneg (x - y))]
end MathesisHard
