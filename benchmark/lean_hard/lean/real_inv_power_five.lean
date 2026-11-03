import Mathlib
namespace MathesisHard
theorem lean_real_inv_power_five : ∀ x : ℝ, x ≠ 0 → x + 1 / x = 3 → x ^ 5 + 1 / x ^ 5 = 123 := by
  intro x hx h
  have h2 : x ^ 2 + 1 / x ^ 2 = 7 := by
    have : x ^ 2 + 1 / x ^ 2 = (x + 1 / x) ^ 2 - 2 := by
      field_simp
      ring
    rw [this, h]; norm_num
  have h3 : x ^ 3 + 1 / x ^ 3 = 18 := by
    have : x ^ 3 + 1 / x ^ 3 = (x + 1 / x) * (x ^ 2 + 1 / x ^ 2) - (x + 1 / x) := by
      field_simp
      ring
    rw [this, h, h2]; norm_num
  have h5 : x ^ 5 + 1 / x ^ 5 = (x ^ 2 + 1 / x ^ 2) * (x ^ 3 + 1 / x ^ 3) - (x + 1 / x) := by
    field_simp
    ring
  rw [h5, h2, h3, h]; norm_num
end MathesisHard
