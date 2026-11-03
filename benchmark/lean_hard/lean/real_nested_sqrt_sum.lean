import Mathlib
namespace MathesisHard
theorem lean_real_nested_sqrt_sum : Real.sqrt (5 + 2 * Real.sqrt 6) + Real.sqrt (5 - 2 * Real.sqrt 6) = 2 * Real.sqrt 3 := by
  have h2 : (0:ℝ) ≤ Real.sqrt 2 := Real.sqrt_nonneg 2
  have h3 : (0:ℝ) ≤ Real.sqrt 3 := Real.sqrt_nonneg 3
  have s2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  have s3 : Real.sqrt 3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  have s6 : Real.sqrt 6 = Real.sqrt 2 * Real.sqrt 3 := by
    rw [← Real.sqrt_mul (by norm_num)]; norm_num
  have lt : Real.sqrt 2 ≤ Real.sqrt 3 := Real.sqrt_le_sqrt (by norm_num)
  have e1 : 5 + 2 * Real.sqrt 6 = (Real.sqrt 3 + Real.sqrt 2) ^ 2 := by
    rw [s6]; nlinarith
  have e2 : 5 - 2 * Real.sqrt 6 = (Real.sqrt 3 - Real.sqrt 2) ^ 2 := by
    rw [s6]; nlinarith
  rw [e1, e2, Real.sqrt_sq (by linarith), Real.sqrt_sq (by linarith)]
  ring
end MathesisHard
