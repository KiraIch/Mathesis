import Mathlib
namespace MathesisHard
theorem lean_ineq_r_vasc_sos : ∀ a b c : ℝ, 3 * (a ^ 3 * b + b ^ 3 * c + c ^ 3 * a) ≤ (a ^ 2 + b ^ 2 + c ^ 2) ^ 2 := by
  intro a b c
  have h : 2 * ((a ^ 2 + b ^ 2 + c ^ 2) ^ 2 - 3 * (a ^ 3 * b + b ^ 3 * c + c ^ 3 * a)) = (a ^ 2 - 2 * a * b + b * c - c ^ 2 + c * a) ^ 2 + (b ^ 2 - 2 * b * c + c * a - a ^ 2 + a * b) ^ 2 + (c ^ 2 - 2 * c * a + a * b - b ^ 2 + b * c) ^ 2 := by ring
  nlinarith [h, sq_nonneg (a ^ 2 - 2 * a * b + b * c - c ^ 2 + c * a), sq_nonneg (b ^ 2 - 2 * b * c + c * a - a ^ 2 + a * b), sq_nonneg (c ^ 2 - 2 * c * a + a * b - b ^ 2 + b * c)]
end MathesisHard
