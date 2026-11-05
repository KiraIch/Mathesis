import Mathlib
namespace MathesisHard
theorem lean_ineq_r_sq_plus_recip : ∀ x : ℝ, 0 < x → 12 ≤ x ^ 2 + 16 / x := by
  intro x hx
  have h : x ^ 2 + 16 / x - 12 = (x - 2) ^ 2 * (x + 4) / x := by field_simp; ring
  have h2 : 0 ≤ (x - 2) ^ 2 * (x + 4) / x := by positivity
  linarith
end MathesisHard
