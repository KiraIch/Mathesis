import Mathlib
namespace MathesisHard
theorem lean_real_sq_lt_self : ∀ x : ℝ, 0 < x → x < 1 → x ^ 2 < x := by
  intro x h0 h1
  nlinarith
end MathesisHard
