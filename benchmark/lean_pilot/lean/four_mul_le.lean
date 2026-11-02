import Mathlib
namespace MathesisPilot
theorem lean_four_mul_le : ∀ (a b : ℝ), 4 * a * b ≤ (a + b) ^ 2 := by
  intro a
  intro b
  have h : 0 ≤ (a - b) ^ 2 := sq_nonneg (a - b)
  nlinarith [h]
end MathesisPilot
