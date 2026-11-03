import Mathlib
namespace MathesisHard
theorem lean_ineq_sq_sum_abc_four : ∀ a b c : ℝ, 0 ≤ a → 0 ≤ b → 0 ≤ c → a + b + c = 3 → 4 ≤ a ^ 2 + b ^ 2 + c ^ 2 + a * b * c := by
  intro a b c ha hb hc h
  have hc' : c = 3 - a - b := by linarith
  subst hc'
  rcases le_total a 1 with h1 | h1 <;> rcases le_total b 1 with h2 | h2
  · nlinarith [mul_nonneg (sub_nonneg.2 h1) (sub_nonneg.2 h2), sq_nonneg (a - b), sq_nonneg (a + b - 2), mul_nonneg ha hb]
  · nlinarith [mul_nonneg (sub_nonneg.2 h1) (sub_nonneg.2 h2), sq_nonneg (a - b), sq_nonneg (a + b - 2), mul_nonneg ha hb, mul_nonneg hb hc]
  · nlinarith [mul_nonneg (sub_nonneg.2 h1) (sub_nonneg.2 h2), sq_nonneg (a - b), sq_nonneg (a + b - 2), mul_nonneg ha hb, mul_nonneg ha hc]
  · nlinarith [mul_nonneg (sub_nonneg.2 h1) (sub_nonneg.2 h2), sq_nonneg (a - b), sq_nonneg (a + b - 2), mul_nonneg ha hb, mul_nonneg ha hc, mul_nonneg hb hc]
end MathesisHard
