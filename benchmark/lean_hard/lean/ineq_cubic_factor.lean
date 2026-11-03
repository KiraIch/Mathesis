import Mathlib
namespace MathesisHard
theorem lean_ineq_cubic_factor : ∀ x : ℝ, 1 ≤ x → 3 * x ^ 2 ≤ 2 * x ^ 3 + 1 := by
  intro x hx
  have h : 0 ≤ (x - 1) ^ 2 * (2 * x + 1) := mul_nonneg (sq_nonneg _) (by linarith)
  nlinarith [h]
end MathesisHard
