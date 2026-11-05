import Mathlib
namespace MathesisHard
theorem lean_real_r_qm_sqrt_pair : ∀ a : ℝ, 1 ≤ a → Real.sqrt (a + 3) + Real.sqrt (a - 1) ≤ 2 * Real.sqrt (a + 1) := by
  intro a ha
  have h : (Real.sqrt (a + 3) + Real.sqrt (a - 1)) ^ 2 ≤ (2 * Real.sqrt (a + 1)) ^ 2 := by
    have e1 : Real.sqrt (a + 3) ^ 2 = a + 3 := Real.sq_sqrt (by linarith)
    have e2 : Real.sqrt (a - 1) ^ 2 = a - 1 := Real.sq_sqrt (by linarith)
    have e3 : Real.sqrt (a + 1) ^ 2 = a + 1 := Real.sq_sqrt (by linarith)
    nlinarith [sq_nonneg (Real.sqrt (a + 3) - Real.sqrt (a - 1))]
  exact le_of_sq_le_sq h (by positivity)
end MathesisHard
