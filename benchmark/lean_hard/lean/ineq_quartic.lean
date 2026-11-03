import Mathlib
namespace MathesisHard
theorem lean_ineq_quartic : ∀ a b : ℝ, a ^ 3 * b + a * b ^ 3 ≤ a ^ 4 + b ^ 4 := by
  intro a b
  have hq : 0 ≤ a ^ 2 + a * b + b ^ 2 := by nlinarith [sq_nonneg (a + b), sq_nonneg a, sq_nonneg b]
  have h : 0 ≤ (a - b) ^ 2 * (a ^ 2 + a * b + b ^ 2) := mul_nonneg (sq_nonneg _) hq
  nlinarith [h]
end MathesisHard
