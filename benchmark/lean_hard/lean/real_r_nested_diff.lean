import Mathlib
namespace MathesisHard
theorem lean_real_r_nested_diff : Real.sqrt (9 + 4 * Real.sqrt 5) - Real.sqrt (9 - 4 * Real.sqrt 5) = 4 := by
  have h : Real.sqrt (9 + 4 * Real.sqrt 5) = Real.sqrt 5 + 2 := by
    have h5 : Real.sqrt 5 ^ 2 = 5 := Real.sq_sqrt (by norm_num)
    rw [Real.sqrt_eq_iff_mul_self_eq (by positivity) (by positivity)]
    nlinarith [h5]
  have h3 : Real.sqrt (9 - 4 * Real.sqrt 5) = Real.sqrt 5 - 2 := by
    have h5 : Real.sqrt 5 ^ 2 = 5 := Real.sq_sqrt (by norm_num)
    have h6 : (2 : ℝ) ≤ Real.sqrt 5 := by nlinarith [Real.sqrt_nonneg 5]
    have h7 : (4 : ℝ) * Real.sqrt 5 ≤ 9 := by nlinarith [Real.sqrt_nonneg 5]
    rw [Real.sqrt_eq_iff_mul_self_eq (by linarith) (by linarith)]
    nlinarith [h5]
  rw [h, h3]
  ring
end MathesisHard
