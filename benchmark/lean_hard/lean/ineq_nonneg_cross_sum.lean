import Mathlib
namespace MathesisHard
theorem lean_ineq_nonneg_cross_sum : ∀ a b c d : ℝ, 0 ≤ a → 0 ≤ b → 0 ≤ c → 0 ≤ d → a * c + b * d ≤ (a + b) * (c + d) := by
  intro a b c d ha hb hc hd
  nlinarith [mul_nonneg ha hd, mul_nonneg hb hc]
end MathesisHard
