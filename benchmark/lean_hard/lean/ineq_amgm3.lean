import Mathlib
namespace MathesisHard
theorem lean_ineq_amgm3 : ∀ a b c : ℝ, 0 ≤ a → 0 ≤ b → 0 ≤ c → 27 * (a * b * c) ≤ (a + b + c) ^ 3 := by
  intro a b c ha hb hc
  have h1 : 0 ≤ (a + b + c) * ((a - b) ^ 2 + (b - c) ^ 2 + (c - a) ^ 2) := mul_nonneg (by linarith) (by positivity)
  nlinarith [h1, mul_nonneg ha (sq_nonneg (b - c)), mul_nonneg hb (sq_nonneg (c - a)), mul_nonneg hc (sq_nonneg (a - b))]
end MathesisHard
