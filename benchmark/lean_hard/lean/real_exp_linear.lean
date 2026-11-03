import Mathlib
namespace MathesisHard
theorem lean_real_exp_linear : ∀ x : ℝ, x ≤ Real.exp x - 1 := by
  intro x
  have h := Real.add_one_le_exp x
  linarith
end MathesisHard
