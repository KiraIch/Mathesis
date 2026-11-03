import Mathlib
namespace MathesisHard
theorem lean_ineq_ratio_two : ∀ a b : ℝ, 0 < a → 0 < b → 2 ≤ a / b + b / a := by
  intro a b ha hb
  have ha' : a ≠ 0 := ha.ne'
  have hb' : b ≠ 0 := hb.ne'
  have h : a / b + b / a - 2 = (a - b) ^ 2 / (a * b) := by
    field_simp
    ring
  have h2 : 0 ≤ (a - b) ^ 2 / (a * b) := div_nonneg (sq_nonneg _) (mul_pos ha hb).le
  linarith
end MathesisHard
