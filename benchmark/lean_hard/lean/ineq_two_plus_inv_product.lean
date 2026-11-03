import Mathlib
namespace MathesisHard
theorem lean_ineq_two_plus_inv_product : ∀ a b : ℝ, 0 < a → 0 < b → a + b = 1 → 25 / 4 ≤ (a + 1 / a) * (b + 1 / b) := by
  intro a b ha hb h
  have hp : 0 < a * b := mul_pos ha hb
  have hab : a * b ≤ 1 / 4 := by nlinarith [sq_nonneg (a - b)]
  have key : (a + 1 / a) * (b + 1 / b) = a * b + 2 / (a * b) - 2 := by
    have hb' : b = 1 - a := by linarith
    subst hb'
    have : a ≠ 0 := ha.ne'
    have : 1 - a ≠ 0 := hb.ne'
    field_simp
    ring
  rw [key]
  have h8 : a * b + 2 / (a * b) - 2 - 25 / 4 = (1 - 4 * (a * b)) * (8 - a * b) / (4 * (a * b)) := by
    field_simp
    ring
  have hnn : 0 ≤ (1 - 4 * (a * b)) * (8 - a * b) / (4 * (a * b)) := by
    apply div_nonneg <;> nlinarith
  linarith
end MathesisHard
