import Mathlib
namespace MathesisHard
theorem lean_real_quartic_pos_sos : ∀ x : ℝ, 0 < x ^ 4 + x ^ 3 + x ^ 2 + x + 1 := by
  intro x
  have h1 : x ^ 4 + x ^ 3 + x ^ 2 + x + 1 = (x ^ 2 + x / 2) ^ 2 + 3 / 4 * (x + 2 / 3) ^ 2 + 2 / 3 := by ring
  nlinarith [sq_nonneg (x ^ 2 + x / 2), sq_nonneg (x + 2 / 3), h1]
end MathesisHard
