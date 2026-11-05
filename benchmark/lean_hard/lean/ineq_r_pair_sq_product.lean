import Mathlib
namespace MathesisHard
theorem lean_ineq_r_pair_sq_product : ∀ a b c : ℝ, 8 * (a * b * c) ^ 2 ≤ (a ^ 2 + b ^ 2) * (b ^ 2 + c ^ 2) * (c ^ 2 + a ^ 2) := by
  intro a b c
  have h : (a ^ 2 + b ^ 2) * (b ^ 2 + c ^ 2) * (c ^ 2 + a ^ 2) - 8 * (a * b * c) ^ 2 = c ^ 2 * (a ^ 2 - b ^ 2) ^ 2 + a ^ 2 * (b ^ 2 - c ^ 2) ^ 2 + b ^ 2 * (c ^ 2 - a ^ 2) ^ 2 := by ring
  have h2 : 0 ≤ c ^ 2 * (a ^ 2 - b ^ 2) ^ 2 + a ^ 2 * (b ^ 2 - c ^ 2) ^ 2 + b ^ 2 * (c ^ 2 - a ^ 2) ^ 2 := by positivity
  linarith
end MathesisHard
