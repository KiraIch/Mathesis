import Mathlib
namespace MathesisHard
theorem lean_real_frac_lt_one : ∀ x : ℝ, 0 < x → x / (x + 1) < 1 := by
  intro x hx
  rw [div_lt_one (by linarith)]
  linarith
end MathesisHard
