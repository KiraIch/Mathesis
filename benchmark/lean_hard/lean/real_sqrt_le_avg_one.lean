import Mathlib
namespace MathesisHard
theorem lean_real_sqrt_le_avg_one : ∀ x : ℝ, 0 ≤ x → Real.sqrt x ≤ (x + 1) / 2 := by
  intro x hx
  nlinarith [Real.sq_sqrt hx, Real.sqrt_nonneg x, sq_nonneg (Real.sqrt x - 1)]
end MathesisHard
