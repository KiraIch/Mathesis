import Mathlib
namespace MathesisHard
theorem lean_ineq_r_inv_sq_pair : ∀ a b : ℝ, 0 < a → 0 < b → 1 / (1 + a * b) ≤ 1 / (1 + a) ^ 2 + 1 / (1 + b) ^ 2 := by
  intro a b ha hb
  have h : 1 / (1 + a) ^ 2 + 1 / (1 + b) ^ 2 - 1 / (1 + a * b) = (a * b * (a - b) ^ 2 + (a * b - 1) ^ 2) / ((1 + a) ^ 2 * (1 + b) ^ 2 * (1 + a * b)) := by field_simp; ring
  have h2 : 0 ≤ (a * b * (a - b) ^ 2 + (a * b - 1) ^ 2) / ((1 + a) ^ 2 * (1 + b) ^ 2 * (1 + a * b)) := by positivity
  linarith
end MathesisHard
