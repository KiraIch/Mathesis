import Mathlib
namespace MathesisPilot
theorem lean_sq_add_one_pos : ∀ (a : ℝ), 0 < a ^ 2 + 1 := by
  intro a
  positivity
end MathesisPilot
