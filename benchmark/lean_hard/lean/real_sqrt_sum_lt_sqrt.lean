import Mathlib
namespace MathesisHard
theorem lean_real_sqrt_sum_lt_sqrt : Real.sqrt 2 + Real.sqrt 3 < Real.sqrt 10 := by
  have h2 : (0:ℝ) ≤ Real.sqrt 2 := Real.sqrt_nonneg 2
  have h3 : (0:ℝ) ≤ Real.sqrt 3 := Real.sqrt_nonneg 3
  have s2 : Real.sqrt 2 ^ 2 = 2 := Real.sq_sqrt (by norm_num)
  have s3 : Real.sqrt 3 ^ 2 = 3 := Real.sq_sqrt (by norm_num)
  have h6 : Real.sqrt 2 * Real.sqrt 3 < 5 / 2 := by
    nlinarith [mul_nonneg h2 h3, sq_nonneg (Real.sqrt 2 * Real.sqrt 3), sq_nonneg (Real.sqrt 2 * Real.sqrt 3 - 5 / 2)]
  apply Real.lt_sqrt_of_sq_lt
  nlinarith
end MathesisHard
