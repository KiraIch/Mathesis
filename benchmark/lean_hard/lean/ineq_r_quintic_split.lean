import Mathlib
namespace MathesisHard
theorem lean_ineq_r_quintic_split : ∀ a b : ℝ, 0 ≤ a → 0 ≤ b → a ^ 2 * b ^ 2 * (a + b) ≤ a ^ 5 + b ^ 5 := by
  intro a b ha hb
  have h : a ^ 5 + b ^ 5 - a ^ 2 * b ^ 2 * (a + b) = (a - b) ^ 2 * (a + b) * (a ^ 2 + a * b + b ^ 2) := by ring
  have h2 : 0 ≤ (a - b) ^ 2 * (a + b) * (a ^ 2 + a * b + b ^ 2) := by positivity
  linarith
end MathesisHard
