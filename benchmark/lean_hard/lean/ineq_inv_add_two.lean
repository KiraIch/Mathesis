import Mathlib
namespace MathesisHard
theorem lean_ineq_inv_add_two : ∀ x : ℝ, 0 < x → 2 ≤ x + 1 / x := by
  intro x hx
  have hx' : x ≠ 0 := hx.ne'
  have h : x + 1 / x - 2 = (x - 1) ^ 2 / x := by
    field_simp
    ring
  have h2 : 0 ≤ (x - 1) ^ 2 / x := div_nonneg (sq_nonneg _) hx.le
  linarith
end MathesisHard
