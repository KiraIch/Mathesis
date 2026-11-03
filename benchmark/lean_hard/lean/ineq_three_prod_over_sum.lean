import Mathlib
namespace MathesisHard
theorem lean_ineq_three_prod_over_sum : ∀ a b c : ℝ, 0 < a → 0 < b → 0 < c → 9 * ((a + b) * (b + c) * (c + a)) ≥ 8 * ((a + b + c) * (a * b + b * c + c * a)) := by
  intro a b c ha hb hc
  have id : (a + b) * (b + c) * (c + a) = (a + b + c) * (a * b + b * c + c * a) - a * b * c := by ring
  have s : (a + b + c) * (a * b + b * c + c * a) ≥ 9 * (a * b * c) := by
    nlinarith [mul_nonneg ha.le (sq_nonneg (b - c)), mul_nonneg hb.le (sq_nonneg (c - a)), mul_nonneg hc.le (sq_nonneg (a - b))]
  rw [id]
  nlinarith [s]
end MathesisHard
