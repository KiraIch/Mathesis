import Mathlib
namespace MathesisHard
theorem lean_real_sq_add_lt_mono : ∀ x y : ℝ, 0 < x → x < y → x ^ 2 + x < y ^ 2 + y := by
  intro x y hx hxy
  nlinarith [mul_pos (sub_pos.mpr hxy) (by linarith : (0:ℝ) < y + x + 1)]
end MathesisHard
