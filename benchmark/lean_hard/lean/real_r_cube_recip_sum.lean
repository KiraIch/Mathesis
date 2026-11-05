import Mathlib
namespace MathesisHard
theorem lean_real_r_cube_recip_sum : ∀ x : ℝ, x ≠ 0 → x + 1 / x = 3 → x ^ 3 + 1 / x ^ 3 = 18 := by
  intro x hx hs
  have h : x ^ 3 + 1 / x ^ 3 = (x + 1 / x) ^ 3 - 3 * (x + 1 / x) := by field_simp; ring
  rw [h, hs]
  norm_num
end MathesisHard
