import Mathlib
namespace MathesisHard
theorem lean_ineq_prod_pairs : ∀ a b c : ℝ, 0 ≤ a → 0 ≤ b → 0 ≤ c → 8 * (a * b * c) ≤ (a + b) * (b + c) * (c + a) := by
  intro a b c ha hb hc
  nlinarith [mul_nonneg ha (sq_nonneg (b - c)), mul_nonneg hb (sq_nonneg (c - a)), mul_nonneg hc (sq_nonneg (a - b))]
end MathesisHard
