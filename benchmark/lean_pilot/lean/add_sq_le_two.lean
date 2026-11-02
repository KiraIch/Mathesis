import Mathlib
namespace MathesisPilot
theorem lean_add_sq_le_two : ∀ (a b : ℝ), (a + b) ^ 2 ≤ 2 * (a ^ 2 + b ^ 2) := by
  intro a
  intro b
  have h : 0 ≤ (a - b) ^ 2 := sq_nonneg (a - b)
  nlinarith [h]
end MathesisPilot
