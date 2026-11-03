import Mathlib
namespace MathesisHard
theorem lean_real_mul_div_le_left : ∀ x y : ℝ, 0 < x → 0 < y → x * y / (x + y) ≤ x := by
  intro x y hx hy
  rw [div_le_iff₀ (by linarith)]
  nlinarith [sq_nonneg x]
end MathesisHard
