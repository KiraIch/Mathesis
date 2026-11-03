import Mathlib
namespace MathesisHard
theorem lean_real_geom_mean_two : ∀ a b : ℝ, 0 ≤ a → 0 ≤ b → 2 * Real.sqrt (a * b) ≤ a + b := by
  intro a b ha hb
  have hs : Real.sqrt (a * b) ^ 2 = a * b := Real.sq_sqrt (mul_nonneg ha hb)
  have h0 : 0 ≤ Real.sqrt (a * b) := Real.sqrt_nonneg (a * b)
  nlinarith [sq_nonneg (a - b), sq_nonneg (a + b - 2 * Real.sqrt (a * b))]
end MathesisHard
