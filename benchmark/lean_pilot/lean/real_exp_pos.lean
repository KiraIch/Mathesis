import Mathlib
namespace MathesisPilot
theorem lean_real_exp_pos : ∀ (x : ℝ), 0 ≤ Real.exp x := by
  intro x
  have h : 0 < Real.exp x := Real.exp_pos x
  exact h.le
end MathesisPilot
